import json
import os
import copy
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from .. import db
from .base import ProviderError
from .context import get_planning_context
from .gemini import GeminiProvider
from .openrouter import OpenRouterProvider
from .offline_parser import parse_offline
from .prompts import build_planning_prompt
from .schemas import ChangeOperation, PlanningIntent, PlanningProposal
from .tools import TOOL_DEFINITIONS, execute_tool
from ..scheduler import schedule as run_schedule, schedule_diff

# Last provider error observed during an actual AI call.  Kept in-memory so
# /ai/provider can report real connection state without making a probe call on
# every status check (Refine.txt §3: provider status reflects real connection
# state, but must stay cheap).  Cleared on a successful call, set on failure.
_LAST_PROVIDER_ERROR: dict | None = None


def _provider_error(exc: Exception) -> dict:
    """Normalize a provider failure into a surfacable error dict."""
    if isinstance(exc, ProviderError):
        return {"kind": exc.kind, "message": str(exc), "retryable": exc.retryable}
    return {"kind": "provider_error", "message": str(exc), "retryable": False}


def last_provider_error() -> dict | None:
    """Return the last observed provider error, if any (for /ai/provider)."""
    return _LAST_PROVIDER_ERROR


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
        return GeminiProvider(key or "", model or "gemini-2.5-flash")
    if provider == "openrouter":
        return OpenRouterProvider(key or "", model or "meta-llama/llama-3.1-8b-instruct:free")
    return None

def extract_and_preview(text: str) -> dict:
    global _LAST_PROVIDER_ERROR
    p = get_provider()
    ai_error = None
    # Try AI provider if configured
    if p is not None and p.is_configured():
        try:
            data = p.extract(text)
            data.setdefault("tasks", [])
            data.setdefault("commitments", [])
            data.setdefault("projects", [])
            data.setdefault("clarifications", [])
            _LAST_PROVIDER_ERROR = None  # successful call clears prior error
            return {"configured": True, "source": "ai", "proposal": data}
        except Exception as exc:
            # Surface provider errors clearly instead of silently falling back.
            # The app stays usable via the offline parser, but the caller can
            # tell AI actually failed (Refine.txt §2).
            ai_error = _provider_error(exc)
            _LAST_PROVIDER_ERROR = ai_error

    # Offline parser fallback (keeps the app usable without a working AI provider).
    data = parse_offline(text)
    data.setdefault("tasks", [])
    data.setdefault("commitments", [])
    data.setdefault("projects", [])
    data.setdefault("clarifications", [])
    result = {
        "configured": False,
        "source": "offline",
        "proposal": data,
        "message": "Parsed using built-in command interpreter (works offline).",
    }
    if ai_error is not None:
        result["ai_error"] = ai_error
        result["message"] = (
            f"AI provider unavailable ({ai_error['kind']}); "
            "using offline fallback."
        )
    return result


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
        "tag", "active_until",
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
            "start_time": item.get("start_time") or "09:00",
            "end_time": item.get("end_time") or "10:00",
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
        "operations": raw.get("operations") or [],
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
    ai_error = None
    global _LAST_PROVIDER_ERROR
    if provider is not None and provider.is_configured():
        try:
            raw = provider.extract(build_planning_prompt(text, context))
            source = _provider_name(provider)
            _LAST_PROVIDER_ERROR = None  # successful call clears prior error
        except Exception as exc:
            # A provider outage must not make the application unusable.
            raw = None
            ai_error = _provider_error(exc)
            _LAST_PROVIDER_ERROR = ai_error
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
        "configured": source != "offline",
        "proposal": proposal.model_dump(mode="json"),
        "context_summary": {
            "projects": len(context["projects"]),
            "tasks": len(context["tasks"]),
            "commitments": len(context["commitments"]),
            "schedule_blocks": len(context["schedule_blocks"]),
        },
    } | ({"ai_error": ai_error,
          "message": f"AI provider unavailable ({ai_error['kind']}); using offline fallback."}
         if ai_error is not None else {})


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
        planned = operator_request(text, conversation_id=conversation_id)
        reply = {"type": "proposal", **planned}

    messages.append({"role": "assistant", "content": reply})
    db.save_conversation(conversation_id, messages)
    return {"conversation_id": conversation_id, **reply}


OPERATOR_SYSTEM = """You are MONOLITH's state-aware planning operator.
Use read tools to inspect the user's actual records before proposing changes.
Never invent IDs, records, availability, or calendar timestamps. Do not modify
the database in this phase: return a JSON change set for review. If the target
is ambiguous, return clarifications instead of guessing. The backend scheduler
will decide concrete calendar slots.

Return JSON only when you are done:
{"summary":"...", "clarifications":[], "assumptions":[],
 "operations":[{"operation":"update|create|delete|set_recurrence",
 "entity_type":"project|task|commitment|milestone", "target_id":123,
 "fields":{}, "reason":"..."}], "tasks":[], "projects":[],
 "commitments":[]}
"""


def _decode_operator_json(content: str) -> dict:
    content = (content or "").strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:]
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("Operator returned malformed structured output") from exc


def _validate_operator_operations(intent: PlanningIntent) -> PlanningIntent:
    """Reject guessed/missing targets before a proposal can be reviewed."""
    clarifications = list(intent.clarifications)
    checked = []
    for operation in intent.operations:
        if operation.operation == "create":
            checked.append(operation)
            continue
        getters = {
            "project": db.get_project,
            "task": db.get_task,
            "commitment": db.get_commitment,
            "milestone": db.get_milestone,
        }
        target = getters[operation.entity_type](operation.target_id)
        if not target:
            clarifications.append(f"I could not find {operation.entity_type} #{operation.target_id}.")
        else:
            checked.append(operation.model_copy(update={"expected_updated_at": target.get("updated_at")}))
    return intent.model_copy(update={"clarifications": list(dict.fromkeys(clarifications)), "operations": checked})


def operator_request(text: str, conversation_id: str | None = None) -> dict:
    """Run a bounded read/inspect/draft loop and persist a reviewable proposal.

    Only read tools are exposed. Mutations are represented as typed operations
    in the proposal and remain subject to the existing approval pipeline.
    """
    if not text or not text.strip():
        raise ValueError("Operator request cannot be empty")
    provider = get_provider()
    if provider is None or not provider.is_configured() or not provider.capabilities().get("tool_calling"):
        return plan_request(text, conversation_id=conversation_id)

    context = get_planning_context(conversation_id)
    compact_context = {
        "timezone": context["settings"].get("timezone", "UTC"),
        "today": datetime.now().date().isoformat(),
        "counts": {key: len(context[key]) for key in ("projects", "tasks", "commitments", "schedule_blocks")},
        "conversation": context.get("conversation"),
        "pending_proposals": db.list_planning_proposals(conversation_id) if conversation_id else [],
    }
    messages = [
        {"role": "system", "content": OPERATOR_SYSTEM + "\nApplication metadata:\n" + json.dumps(compact_context, default=str)},
        {"role": "user", "content": text.strip()},
    ]
    max_turns = 8
    all_tool_events = []
    for _ in range(max_turns):
        try:
            turn = provider.chat_turn(messages, tools=provider.tool_schemas())
        except Exception as exc:
            global _LAST_PROVIDER_ERROR
            _LAST_PROVIDER_ERROR = _provider_error(exc)
            return plan_request(text, conversation_id=conversation_id) | {"ai_error": _LAST_PROVIDER_ERROR, "operator_fallback": True}
        calls = turn.get("tool_calls") or []
        if not calls:
            raw = _decode_operator_json(turn.get("content", ""))
            try:
                intent = _normalize_raw_intent(raw)
            except (ValidationError, TypeError, ValueError) as exc:
                raise ValueError(f"Operator response failed validation: {exc}") from exc
            intent = _validate_operator_operations(intent)
            proposal = PlanningProposal(
                request_text=text.strip(), source=_provider_name(provider), intent=intent,
                risk_level="high" if intent.operations else "medium" if intent.clarifications else "low",
            )
            stored = db.create_planning_proposal({
                "conversation_id": conversation_id,
                "request_text": proposal.request_text,
                "source": proposal.source,
                "structured_plan": proposal.model_dump(mode="json"),
            })
            return {
                "proposal_id": stored["id"], "intent_type": classify_request(text),
                "source": _provider_name(provider), "configured": True,
                "proposal": proposal.model_dump(mode="json"),
                "operator": {"turns": len(all_tool_events) + 1, "tool_events": all_tool_events},
            }
        assistant_message = {"role": "assistant", "content": turn.get("content", ""), "tool_calls": calls}
        messages.append(assistant_message)
        for call in calls:
            name = call.get("name")
            definition = TOOL_DEFINITIONS.get(name)
            if not definition or definition["risk"] != "read":
                result = {"name": name, "success": False, "error": "Only read tools are available during operator inspection."}
            else:
                result = execute_tool(name, call.get("arguments") or {}, conversation_id=conversation_id)
            all_tool_events.append({"name": name, "success": result.get("success"), "error": result.get("error")})
            messages.append({"role": "tool", "tool_name": name, "tool_call_id": call.get("id"), "content": json.dumps(result, default=str)})
    raise ValueError("Operator exceeded the maximum of 8 inspection turns")


def _proposal_intent(proposal: dict) -> dict:
    return proposal.get("structured_plan", {}).get("intent", {})


def _validate_change_set(intent: dict, settings: dict):
    operations = intent.get("operations", [])
    limit = int(settings.get("ai_max_mutations", 25))
    if len(operations) > limit:
        raise ValueError(f"Proposal contains {len(operations)} mutations; limit is {limit}")
    if settings.get("ai_require_delete_confirmation", True):
        deletes = [op for op in operations if op.get("operation") == "delete"]
        if deletes and settings.get("ai_autonomy") == "suggestion":
            raise ValueError("Delete operations require assisted or full autonomy plus explicit approval")
    return operations


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

    affected = {"task": set(), "commitment": set(), "project": set(), "milestone": set()}
    # Operations are applied to copies only. They become real changes only in
    # the transactional approval path.
    for operation in intent.get("operations", []):
        entity = operation["entity_type"]
        op = operation["operation"]
        target_id = operation.get("target_id")
        fields = dict(operation.get("fields") or {})
        rows = {"task": tasks, "commitment": commitments, "project": projects}.get(entity, [])
        if op == "create":
            if entity == "project":
                record = {**fields, "id": next_id, "name": fields.get("name", "Untitled project")}
                next_id -= 1
                projects.append(record)
            elif entity == "task":
                record = {**fields, "id": next_id, "title": fields.get("title", "Untitled task"), "remaining_minutes": fields.get("remaining_minutes", fields.get("estimated_minutes", 60)), "status": "todo", "dependencies": fields.get("dependencies", []), "preferred_days": fields.get("preferred_days", [])}
                next_id -= 1
                tasks.append(record)
            elif entity == "commitment":
                record = {**fields, "id": next_id, "title": fields.get("title", "Untitled commitment"), "days_of_week": fields.get("days_of_week", [])}
                next_id -= 1
                commitments.append(record)
            continue
        record = next((row for row in rows if row.get("id") == target_id), None)
        if not record:
            continue
        affected[entity].add(target_id)
        if op in ("update", "set_recurrence"):
            record.update(fields)
        elif op == "delete":
            rows.remove(record)
    return tasks, commitments, projects, affected


def _filter_affected_existing_blocks(blocks, affected):
    """Remove stale future generated rows for changed domain records."""
    now = datetime.now().replace(microsecond=0).isoformat()
    result = []
    for block in blocks:
        entity = "task" if block.get("task_id") is not None else "commitment" if block.get("commitment_id") is not None else None
        target = block.get("task_id") if entity == "task" else block.get("commitment_id")
        if entity and target in affected.get(entity, set()) and block.get("status") == "scheduled" and block.get("start_dt", "") >= now:
            # Generated task blocks are flexible; generated commitment rows are
            # rebuilt from the updated recurrence. Historical/complete rows stay.
            continue
        result.append(block)
    return result


def preview_proposal(proposal_id: int) -> dict:
    stored = db.get_planning_proposal(proposal_id)
    if not stored:
        raise ValueError("Planning proposal not found")
    if stored["status"] not in ("draft", "previewed"):
        raise ValueError(f"Proposal is already {stored['status']}")

    context = get_planning_context()
    intent = _proposal_intent(stored)
    _validate_change_set(intent, context["settings"])
    tasks, commitments, projects, affected = _preview_inputs(intent, context)
    existing_blocks = _filter_affected_existing_blocks(context["schedule_blocks"], affected)
    new_blocks, unscheduled = run_schedule(
        tasks,
        commitments,
        context["settings"],
        existing_blocks,
        projects=projects,
        horizon_days=int(context["settings"].get("ai_max_horizon_days", 180)),
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
        "change_set": {
            "operations": intent.get("operations", []),
            "affected": {key: sorted(value) for key, value in affected.items() if value},
        },
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
    if db.get_settings().get("ai_dry_run"):
        return {"proposal_id": proposal_id, "status": "dry_run", "created": {}, "schedule": preview}
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


def revert_proposal(proposal_id: int) -> dict:
    """Revert the last approved change set, then regenerate the calendar."""
    result = db.revert_planning_proposal(proposal_id)
    # Domain rows and future flexible blocks are restored transactionally;
    # schedule regeneration remains deterministic and preserves history.
    from ..routers.schedule import regenerate
    schedule_result = regenerate()
    return {"proposal_id": proposal_id, "status": "reverted", "reverted": result, "schedule": schedule_result}

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
