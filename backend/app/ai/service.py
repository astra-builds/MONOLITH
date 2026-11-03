import os
from typing import Any

from pydantic import ValidationError

from .. import db
from .context import get_planning_context
from .gemini import GeminiProvider
from .openrouter import OpenRouterProvider
from .offline_parser import parse_offline
from .prompts import build_planning_prompt
from .schemas import PlanningIntent, PlanningProposal
from .tools import execute_tool
from ..scheduler import schedule as run_schedule, schedule_diff

def get_provider():
    s = db.get_settings()
    provider = s.get("ai_provider", "none")
    if provider == "none":
        # env fallback
        if os.environ.get("GEMINI_API_KEY"):
            provider = "gemini"
        elif os.environ.get("OPENROUTER_API_KEY"):
            provider = "openrouter"
    key = s.get("ai_api_key", "") or (os.environ.get("GEMINI_API_KEY") if provider=="gemini" else os.environ.get("OPENROUTER_API_KEY"))
    model = s.get("ai_model", "") or (os.environ.get("GEMINI_MODEL") if provider=="gemini" else os.environ.get("OPENROUTER_MODEL"))
    if provider == "gemini":
        return GeminiProvider(key or "", model or "gemini-1.5-flash")
    if provider == "openrouter":
        return OpenRouterProvider(key or "", model or "meta-llama/llama-3.1-8b-instruct:free")
    return None

def extract_and_preview(text: str) -> dict:
    p = get_provider()
    # Try AI provider if configured
    if p is not None and p.is_configured():
        try:
            data = p.extract(text)
            data.setdefault("tasks", [])
            data.setdefault("commitments", [])
            data.setdefault("projects", [])
            data.setdefault("clarifications", [])
            return {"configured": True, "source": "ai", "proposal": data}
        except Exception as e:
            # Fall back to offline parser on AI error
            pass

    # Seamless offline parser fallback
    data = parse_offline(text)
    data.setdefault("tasks", [])
    data.setdefault("commitments", [])
    data.setdefault("projects", [])
    data.setdefault("clarifications", [])
    return {
        "configured": False,
        "source": "offline",
        "proposal": data,
        "message": "Parsed using built-in command interpreter (works offline).",
    }


def classify_request(text: str) -> str:
    """Classify intent before planning; this is deliberately deterministic."""
    lower = text.lower()
    if any(word in lower for word in ("completed", "finished", "done with")):
        return "complete_activity"
    if any(word in lower for word in ("missed", "skip", "can't study", "cannot study")):
        return "modify_plan"
    if any(word in lower for word in ("move", "reschedule", "make ", "change availability")):
        return "modify_plan"
    if any(word in lower for word in ("when is", "how much progress", "progress", "what's next")):
        return "progress_question"
    if any(word in lower for word in ("project", "course", "class", "lecture", "study", "task")):
        return "new_plan"
    return "general_question"


def _provider_name(provider) -> str:
    if isinstance(provider, GeminiProvider):
        return "gemini"
    if isinstance(provider, OpenRouterProvider):
        return "openrouter"
    return "offline"


def _clean_task(raw: dict[str, Any], project_name: str | None = None) -> dict:
    allowed = {
        "title", "description", "estimated_minutes", "estimate_source",
        "estimate_confidence", "deadline", "priority", "preferred_days",
        "preferred_start", "preferred_end", "min_session_minutes",
        "max_session_minutes", "splittable", "flexible", "dependencies",
        "project_name",
    }
    task = {key: value for key, value in raw.items() if key in allowed}
    if project_name and not task.get("project_name"):
        task["project_name"] = project_name
    if "remaining_minutes" in raw and "estimated_minutes" not in task:
        task["estimated_minutes"] = raw["remaining_minutes"]
    task.setdefault("estimate_source", "unknown")
    return task


def _normalize_raw_intent(raw: dict) -> PlanningIntent:
    """Convert provider/offline legacy extraction into the canonical schema."""
    projects = []
    project_names = set()
    for item in raw.get("projects", []) or []:
        name = item.get("name") or item.get("title")
        if not name:
            continue
        project_names.add(name)
        projects.append({
            "name": name,
            "description": item.get("description", ""),
            "kind": item.get("kind", "project"),
            "total_sessions": item.get("total_sessions", 0),
            "session_minutes": item.get("session_minutes", 60),
            "target_deadline": item.get("target_deadline"),
            "milestones": item.get("milestones", []),
            "tasks": [],
        })

    tasks = [_clean_task(item) for item in (raw.get("tasks", []) or [])]
    for task in tasks:
        if task.get("project_name") not in project_names:
            task.pop("project_name", None)

    commitments = []
    for item in raw.get("commitments", []) or []:
        commitments.append({
            "title": item.get("title") or item.get("name") or "Untitled commitment",
            "kind": item.get("kind", "fixed"),
            "tag": item.get("tag", "personal"),
            "recurrence": item.get("recurrence", "weekly"),
            "days_of_week": item.get("days_of_week", []),
            "start_time": item.get("start_time", "09:00"),
            "end_time": item.get("end_time", "10:00"),
            "start_date": item.get("start_date"),
            "end_date": item.get("end_date"),
            "one_time_date": item.get("one_time_date"),
        })

    # Do not pass provider-specific wrapper fields through a strict schema.
    intent = {
        "summary": raw.get("summary", ""),
        "projects": projects,
        "tasks": tasks,
        "commitments": commitments,
        "constraints": raw.get("constraints") or {},
        "clarifications": raw.get("clarifications") or [],
        "assumptions": raw.get("assumptions") or [],
    }
    return PlanningIntent.model_validate(intent)


def _remove_redundant_clarifications(intent: PlanningIntent, context: dict) -> PlanningIntent:
    existing_names = {p["name"].casefold() for p in context["projects"]}
    questions = []
    for question in intent.clarifications:
        # The offline parser uses this message for a harmless default. Keep
        # genuinely blocking questions, but don't repeatedly ask for data the
        # parser has already supplied.
        if "defaulted to" in question.lower() and intent.projects:
            continue
        questions.append(question)
    if len(existing_names) != len(context["projects"]):
        questions.append("More than one existing project has the same name; which one should this plan update?")
    return intent.model_copy(update={"clarifications": questions})


def plan_request(text: str, conversation_id: str | None = None) -> dict:
    """Build and persist a validated, non-mutating planning proposal."""
    if not text or not text.strip():
        raise ValueError("Planning request cannot be empty")

    context = get_planning_context(conversation_id)
    provider = get_provider()
    source = "offline"
    raw = None
    if provider is not None and provider.is_configured():
        try:
            raw = provider.extract(build_planning_prompt(text, context))
            source = _provider_name(provider)
        except Exception:
            # A provider outage must not make the application unusable.
            raw = None
    if raw is None:
        raw = parse_offline(text)

    try:
        intent = _normalize_raw_intent(raw)
    except (ValidationError, TypeError, ValueError) as exc:
        raise ValueError(f"Planning response failed validation: {exc}") from exc
    intent = _remove_redundant_clarifications(intent, context)
    proposal = PlanningProposal(
        request_text=text.strip(),
        source=source,
        intent=intent,
        risk_level="medium" if intent.clarifications else "low",
    )
    stored = db.create_planning_proposal({
        "conversation_id": conversation_id,
        "request_text": proposal.request_text,
        "source": proposal.source,
        "structured_plan": proposal.model_dump(mode="json"),
    })
    return {
        "proposal_id": stored["id"],
        "intent_type": classify_request(text),
        "source": source,
        "proposal": proposal.model_dump(mode="json"),
        "context_summary": {
            "projects": len(context["projects"]),
            "tasks": len(context["tasks"]),
            "commitments": len(context["commitments"]),
            "schedule_blocks": len(context["schedule_blocks"]),
        },
    }


def _resolve_task_reference(text: str):
    """Resolve a follow-up reference against current records, never guesses."""
    lower = text.casefold()
    tasks = db.list_tasks()
    matches = [task for task in tasks if task["title"].casefold() in lower or lower in task["title"].casefold()]
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, "I found multiple matching tasks. Please name the task explicitly."
    # Handle common ordinal lecture references such as "lecture three".
    ordinal = {"one": "01", "two": "02", "three": "03", "four": "04", "five": "05"}
    for word, number in ordinal.items():
        if word in lower and "lecture" in lower:
            matches = [task for task in tasks if "lecture" in task["title"].casefold() and number in task["title"]]
            if len(matches) == 1:
                return matches[0], None
    return None, "I couldn't identify the task you mean."


def handle_conversation_message(conversation_id: str, text: str, confirm: bool = False) -> dict:
    conversation = db.get_conversation(conversation_id)
    messages = conversation.get("messages", [])[-19:]
    messages.append({"role": "user", "content": text})
    lower = text.casefold()
    action = None
    if any(phrase in lower for phrase in ("completed", "finished", "done with")):
        task, clarification = _resolve_task_reference(text)
        if clarification:
            reply = {"type": "clarification", "message": clarification}
        else:
            action = execute_tool("complete_task", {"task_id": task["id"]}, confirmed=confirm, conversation_id=conversation_id)
            reply = {"type": "tool_result", "tool": action, "message": "Task completion recorded." if action.get("success") else "Confirmation is required before changing this task."}
    elif any(phrase in lower for phrase in ("skip", "can't study", "cannot study", "missed")):
        task, clarification = _resolve_task_reference(text)
        if clarification:
            reply = {"type": "clarification", "message": clarification}
        else:
            action = execute_tool("skip_task", {"task_id": task["id"]}, confirmed=confirm, conversation_id=conversation_id)
            reply = {"type": "tool_result", "tool": action, "message": "Confirmation is required before skipping scheduled work." if action.get("confirmation_required") else "Task skipped."}
    elif "what's next" in lower or "what is next" in lower:
        action = execute_tool("get_tasks", {"status": "todo"}, conversation_id=conversation_id)
        reply = {"type": "tool_result", "tool": action, "message": "Here are your remaining tasks."}
    else:
        planned = plan_request(text, conversation_id=conversation_id)
        reply = {"type": "proposal", **planned}

    messages.append({"role": "assistant", "content": reply})
    db.save_conversation(conversation_id, messages)
    return {"conversation_id": conversation_id, **reply}


def _proposal_intent(proposal: dict) -> dict:
    return proposal.get("structured_plan", {}).get("intent", {})


def _preview_inputs(intent: dict, context: dict):
    """Build scheduler records using negative IDs for unpersisted proposals."""
    projects = list(context["projects"])
    project_by_name = {p["name"].casefold(): p for p in projects}
    next_id = -1
    project_ids = {}
    for project in intent.get("projects", []):
        name = project["name"]
        existing = project_by_name.get(name.casefold())
        if existing:
            project_ids[name.casefold()] = existing["id"]
        else:
            project_ids[name.casefold()] = next_id
            projects.append({
                "id": next_id,
                "name": name,
                "kind": project.get("kind", "project"),
                "total_sessions": project.get("total_sessions", 0),
                "session_minutes": project.get("session_minutes", 60),
            })
            next_id -= 1

    tasks = list(context["tasks"])
    task_ids_by_title = {task["title"].casefold(): task["id"] for task in tasks}
    proposed_tasks = []
    for project in intent.get("projects", []):
        for task in project.get("tasks", []):
            proposed_tasks.append({**task, "project_name": project["name"]})
    proposed_tasks.extend(intent.get("tasks", []))

    new_task_ids = {}
    for raw in proposed_tasks:
        task = dict(raw)
        task_id = next_id
        next_id -= 1
        task["id"] = task_id
        task["project_id"] = project_ids.get((task.get("project_name") or "").casefold())
        task["remaining_minutes"] = task.get("estimated_minutes", 60)
        task["status"] = "todo"
        resolved = []
        for dependency in task.get("dependencies", []):
            if dependency == "__PREV__" and proposed_tasks:
                previous = proposed_tasks[len(new_task_ids) - 1] if new_task_ids else None
                if previous:
                    resolved.append(new_task_ids.get(previous.get("title", "").casefold()))
            elif isinstance(dependency, int):
                resolved.append(dependency)
            elif isinstance(dependency, str):
                resolved_id = new_task_ids.get(dependency.casefold()) or task_ids_by_title.get(dependency.casefold())
                if resolved_id is not None:
                    resolved.append(resolved_id)
        task["dependencies"] = [value for value in resolved if value is not None]
        new_task_ids[task.get("title", "").casefold()] = task_id
        tasks.append(task)

    commitments = list(context["commitments"])
    for raw in intent.get("commitments", []):
        commitment = dict(raw)
        commitment["id"] = next_id
        next_id -= 1
        commitments.append(commitment)
    return tasks, commitments, projects


def preview_proposal(proposal_id: int) -> dict:
    stored = db.get_planning_proposal(proposal_id)
    if not stored:
        raise ValueError("Planning proposal not found")
    if stored["status"] not in ("draft", "previewed"):
        raise ValueError(f"Proposal is already {stored['status']}")

    context = get_planning_context()
    intent = _proposal_intent(stored)
    tasks, commitments, projects = _preview_inputs(intent, context)
    new_blocks, unscheduled = run_schedule(
        tasks,
        commitments,
        context["settings"],
        context["schedule_blocks"],
        projects=projects,
        horizon_days=180,
    )

    # The scheduler intentionally emits fixed intervals and preserved rows.
    # Collapse exact duplicates for a clean proposal preview.
    unique_blocks = []
    seen = set()
    for block in new_blocks:
        key = (block.get("task_id"), block.get("commitment_id"), block["title"], block["start_dt"], block["end_dt"])
        if key not in seen:
            seen.add(key)
            unique_blocks.append(block)

    diff = schedule_diff(context["schedule_blocks"], unique_blocks)
    projected = {}
    for block in unique_blocks:
        if block.get("task_id") is not None:
            projected[str(block["task_id"])] = max(
                projected.get(str(block["task_id"]), ""), block["end_dt"]
            )
    preview = {
        "blocks": unique_blocks,
        "diff": diff,
        "unscheduled": unscheduled,
        "projected_completion_dates": projected,
    }
    updated = db.update_planning_proposal(proposal_id, {
        "status": "previewed",
        "schedule_preview": preview,
    })
    return {
        "proposal_id": proposal_id,
        "status": updated["status"],
        "preview": preview,
        "proposal": updated,
    }


def approve_proposal(proposal_id: int) -> dict:
    stored = db.get_planning_proposal(proposal_id)
    if not stored:
        raise ValueError("Planning proposal not found")
    if stored["status"] not in ("draft", "previewed"):
        raise ValueError(f"Proposal is already {stored['status']}")

    # Re-preview against current state immediately before applying. This
    # prevents approval from applying a stale calendar proposal.
    current_preview = preview_proposal(proposal_id)
    preview = current_preview["preview"]
    result = db.apply_planning_proposal_transaction(
        proposal_id,
        _proposal_intent(stored),
        preview["blocks"],
    )
    return {
        "proposal_id": proposal_id,
        "status": "approved",
        "created": result,
        "schedule": preview,
    }

def apply_proposal(proposal: dict) -> dict:
    # create projects, tasks, commitments in DB. Does not schedule.
    created = {"projects": [], "tasks": [], "commitments": []}
    project_id_map = {}

    # 1. Projects
    for pr in proposal.get("projects", []):
        p = db.create_project(pr)
        created["projects"].append(p)
        project_id_map[pr["name"]] = p["id"]

    # 2. Tasks with sequential dependency resolution
    prev_task_id = None
    for t in proposal.get("tasks", []):
        data = dict(t)
        # Link project
        if "project_name" in data and data["project_name"] in project_id_map:
            data["project_id"] = project_id_map[data["project_name"]]

        # Resolve sequential dependency token
        raw_deps = data.get("dependencies", [])
        resolved_deps = []
        for d in raw_deps:
            if d == "__PREV__" and prev_task_id is not None:
                resolved_deps.append(prev_task_id)
            elif isinstance(d, int):
                resolved_deps.append(d)
        data["dependencies"] = resolved_deps

        if data.get("remaining_minutes") is None:
            data["remaining_minutes"] = data.get("estimated_minutes", 60)

        task = db.create_task(data)
        created["tasks"].append(task)
        prev_task_id = task["id"]

    # 3. Commitments
    for c in proposal.get("commitments", []):
        cm = db.create_commitment(c)
        created["commitments"].append(cm)

    return created
