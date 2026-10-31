import os
from .. import db
from .gemini import GeminiProvider
from .openrouter import OpenRouterProvider
from .offline_parser import parse_offline

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
