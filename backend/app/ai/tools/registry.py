"""Validated application tools available to the AI operator."""

import hashlib
import json
from datetime import datetime

from ... import db
from ...scheduler import parse_dt


TOOL_DEFINITIONS = {
    "get_calendar_events": {"description": "Read schedule blocks in an optional date range", "risk": "read", "parameters": {"type": "object", "properties": {"start": {"type": "string"}, "end": {"type": "string"}}, "additionalProperties": False}},
    "get_projects": {"description": "Read projects and milestones", "risk": "read", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "additionalProperties": False}},
    "get_tasks": {"description": "Read tasks, optionally filtered by project or status", "risk": "read", "parameters": {"type": "object", "properties": {"project_id": {"type": "integer"}, "status": {"type": "string"}, "query": {"type": "string"}}, "additionalProperties": False}},
    "get_commitments": {"description": "Read fixed and recurring commitments, optionally filtered by weekday/tag", "risk": "read", "parameters": {"type": "object", "properties": {"tag": {"type": "string"}, "weekday": {"type": "integer", "minimum": 0, "maximum": 6}, "query": {"type": "string"}}, "additionalProperties": False}},
    "resolve_records": {"description": "Resolve a natural-language reference to candidate records without guessing", "risk": "read", "parameters": {"type": "object", "properties": {"entity_type": {"type": "string", "enum": ["project", "task", "commitment", "milestone"]}, "query": {"type": "string"}, "weekday": {"type": "integer", "minimum": 0, "maximum": 6}}, "required": ["entity_type", "query"], "additionalProperties": False}},
    "get_conversation_state": {"description": "Read pending proposals and recent conversation state", "risk": "read", "parameters": {"type": "object", "properties": {"conversation_id": {"type": "string"}}, "required": ["conversation_id"], "additionalProperties": False}},
    "get_project_progress": {"description": "Read project progress and completion estimate", "risk": "read", "parameters": {"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"], "additionalProperties": False}},
    "inspect_scheduling_conflicts": {"description": "Inspect actual unscheduled work and scheduling conflicts", "risk": "read", "parameters": {"type": "object", "properties": {"start": {"type": "string"}, "end": {"type": "string"}}, "additionalProperties": False}},
    "preview_schedule": {"description": "Generate a deterministic proposal schedule preview", "risk": "read", "parameters": {"type": "object", "properties": {"proposal_id": {"type": "integer"}}, "required": ["proposal_id"], "additionalProperties": False}},
    "create_project": {"description": "Create a project", "risk": "consequential", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "kind": {"type": "string"}, "target_deadline": {"type": ["string", "null"]}}, "required": ["name"], "additionalProperties": False}},
    "update_project": {"description": "Update an existing project", "risk": "consequential", "parameters": {"type": "object", "properties": {"project_id": {"type": "integer"}, "name": {"type": "string"}, "description": {"type": "string"}, "kind": {"type": "string"}, "target_deadline": {"type": ["string", "null"]}}, "required": ["project_id"], "additionalProperties": False}},
    "create_task": {"description": "Create a task or bounded routine work item", "risk": "consequential", "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "estimated_minutes": {"type": "integer"}, "deadline": {"type": ["string", "null"]}, "tag": {"type": ["string", "null"]}, "active_until": {"type": ["string", "null"]}}, "required": ["title"], "additionalProperties": False}},
    "update_task": {"description": "Update an existing task", "risk": "consequential", "parameters": {"type": "object", "properties": {"task_id": {"type": "integer"}, "title": {"type": "string"}, "description": {"type": "string"}, "deadline": {"type": ["string", "null"]}, "tag": {"type": ["string", "null"]}, "active_until": {"type": ["string", "null"]}, "status": {"type": "string"}}, "required": ["task_id"], "additionalProperties": False}},
    "delete_task": {"description": "Delete an existing task", "risk": "destructive", "parameters": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"], "additionalProperties": False}},
    "create_commitment": {"description": "Create a recurring or one-time commitment", "risk": "consequential", "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "tag": {"type": "string"}, "recurrence": {"type": "string"}, "days_of_week": {"type": "array", "items": {"type": "integer"}}, "start_time": {"type": "string"}, "end_time": {"type": "string"}, "start_date": {"type": ["string", "null"]}, "end_date": {"type": ["string", "null"]}}, "required": ["title", "start_time", "end_time"], "additionalProperties": False}},
    "update_commitment": {"description": "Update an existing commitment", "risk": "consequential", "parameters": {"type": "object", "properties": {"commitment_id": {"type": "integer"}, "title": {"type": "string"}, "tag": {"type": "string"}, "days_of_week": {"type": "array", "items": {"type": "integer"}}, "start_time": {"type": "string"}, "end_time": {"type": "string"}, "start_date": {"type": ["string", "null"]}, "end_date": {"type": ["string", "null"]}}, "required": ["commitment_id"], "additionalProperties": False}},
    "complete_task": {"description": "Mark a task complete", "risk": "safe_write", "parameters": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"], "additionalProperties": False}},
    "skip_task": {"description": "Skip a task and refund scheduled time", "risk": "consequential", "parameters": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"], "additionalProperties": False}},
    "update_availability": {"description": "Add an availability rule", "risk": "consequential", "parameters": {"type": "object", "properties": {"weekday": {"type": "integer"}, "start_time": {"type": "string"}, "end_time": {"type": "string"}, "available": {"type": "boolean"}}, "required": ["weekday", "start_time", "end_time"], "additionalProperties": False}},
}


def tool_schemas(*, read_only=False):
    """Return OpenAI-compatible schemas; providers adapt this to native shape."""
    items = TOOL_DEFINITIONS.items()
    if read_only:
        items = ((name, definition) for name, definition in items if definition["risk"] == "read")
    return [{"type": "function", "function": {"name": name, "description": definition["description"], "parameters": definition["parameters"]}} for name, definition in items]


def _read_tool(name, args):
    if name == "get_calendar_events":
        return db.list_blocks(args.get("start"), args.get("end"))
    if name == "get_projects":
        rows = db.list_projects()
        query = (args.get("query") or "").casefold()
        return [row for row in rows if not query or query in row["name"].casefold() or query in (row.get("description") or "").casefold()]
    if name == "get_tasks":
        rows = db.list_tasks(args.get("project_id"), args.get("status"))
        query = (args.get("query") or "").casefold()
        return [row for row in rows if not query or query in row["title"].casefold() or query in (row.get("description") or "").casefold()]
    if name == "get_commitments":
        rows = db.list_commitments(args.get("tag"))
        if args.get("weekday") is not None:
            rows = [row for row in rows if args["weekday"] in (row.get("days_of_week") or [])]
        query = (args.get("query") or "").casefold()
        return [row for row in rows if not query or query in row["title"].casefold()]
    if name == "resolve_records":
        entity = args["entity_type"]
        query = args["query"].casefold().strip()
        if entity == "project":
            rows = db.list_projects()
            label = lambda row: f"{row['name']} {row.get('description', '')}"
        elif entity == "task":
            rows = db.list_tasks()
            label = lambda row: f"{row['title']} {row.get('description', '')}"
        elif entity == "commitment":
            rows = db.list_commitments()
            if args.get("weekday") is not None:
                rows = [row for row in rows if args["weekday"] in (row.get("days_of_week") or [])]
            label = lambda row: row["title"]
        elif entity == "milestone":
            rows = db.list_milestones()
            label = lambda row: f"{row['title']} {row.get('description', '')}"
        else:
            raise ValueError("Unsupported entity type")
        candidates = [row for row in rows if query in label(row).casefold()]
        return {"entity_type": entity, "query": args["query"], "match_count": len(candidates), "ambiguous": len(candidates) > 1, "candidates": candidates[:25]}
    if name == "get_conversation_state":
        conversation_id = args["conversation_id"]
        return {"conversation": db.get_conversation(conversation_id), "pending_proposals": [p for p in db.list_planning_proposals() if p.get("conversation_id") == conversation_id and p.get("status") in ("draft", "previewed")]}
    if name == "get_project_progress":
        project = db.get_project(int(args["project_id"]))
        if not project:
            raise ValueError("Project not found")
        tasks = db.list_tasks(project_id=project["id"])
        blocks = [b for b in db.list_blocks() if b.get("task_id") in {t["id"] for t in tasks}]
        done = sum(t["status"] == "done" for t in tasks)
        return {
            "project": project,
            "progress_percent": done / len(tasks) * 100 if tasks else 0,
            "completed_tasks": done,
            "remaining_tasks": len(tasks) - done,
            "estimated_completion": max((b["end_dt"] for b in blocks), default=None),
        }
    if name == "inspect_scheduling_conflicts":
        from ...scheduler import schedule
        result, unscheduled = schedule(
            db.list_tasks(), db.list_commitments(), db.get_settings(),
            db.list_blocks(args.get("start"), args.get("end")),
            projects=db.list_projects(), horizon_days=180,
        )
        return {"unscheduled": unscheduled, "scheduled_count": len(result), "message": "Deterministic conflict analysis completed."}
    if name == "preview_schedule":
        from ..service import preview_proposal
        return preview_proposal(int(args["proposal_id"]))
    raise ValueError(f"Unknown read tool: {name}")


def _write_tool(name, args):
    if name == "create_project":
        return db.create_project(args)
    if name == "update_project":
        project_id = int(args["project_id"])
        data = {key: value for key, value in args.items() if key != "project_id"}
        result = db.update_project(project_id, data)
        if not result:
            raise ValueError("Project not found")
        return result
    if name == "create_task":
        data = {key: value for key, value in args.items() if key != "task_id"}
        return db.create_task(data)
    if name == "update_task":
        task_id = int(args["task_id"])
        data = {key: value for key, value in args.items() if key != "task_id"}
        result = db.update_task(task_id, data)
        if not result:
            raise ValueError("Task not found")
        return result
    if name == "delete_task":
        task_id = int(args["task_id"])
        if not db.get_task(task_id):
            raise ValueError("Task not found")
        db.delete_task(task_id)
        return {"deleted_task_id": task_id}
    if name == "create_commitment":
        return db.create_commitment(args)
    if name == "update_commitment":
        commitment_id = int(args["commitment_id"])
        data = {key: value for key, value in args.items() if key != "commitment_id"}
        result = db.update_commitment(commitment_id, data)
        if not result:
            raise ValueError("Commitment not found")
        return result
    if name == "complete_task":
        task = db.get_task(int(args["task_id"]))
        if not task:
            raise ValueError("Task not found")
        db.update_task(task["id"], {"status": "done", "remaining_minutes": 0, "completed_at": db.now_iso()})
        for block in db.list_blocks():
            if block.get("task_id") == task["id"] and block["status"] == "scheduled":
                db.update_block(block["id"], {"status": "completed"})
        return db.get_task(task["id"])
    if name == "skip_task":
        task = db.get_task(int(args["task_id"]))
        if not task:
            raise ValueError("Task not found")
        for block in db.list_blocks():
            if block.get("task_id") == task["id"] and block["status"] == "scheduled":
                minutes = int((parse_dt(block["end_dt"]) - parse_dt(block["start_dt"])).total_seconds() / 60)
                db.update_block(block["id"], {"status": "skipped"})
                task = db.get_task(task["id"])
                db.update_task(task["id"], {"remaining_minutes": (task.get("remaining_minutes") or 0) + minutes})
        return db.get_task(task["id"])
    if name == "update_availability":
        return db.create_availability_rule({
            "weekday": int(args["weekday"]),
            "start_time": args["start_time"],
            "end_time": args["end_time"],
            "available": args.get("available", True),
            "source": "ai",
        })
    raise ValueError(f"Unknown write tool: {name}")


def execute_tool(name, arguments=None, *, confirmed=False, conversation_id=None):
    arguments = arguments or {}
    definition = TOOL_DEFINITIONS.get(name)
    if not definition:
        return {"name": name, "success": False, "error": "Tool is not registered"}
    autonomy = db.get_settings().get("ai_autonomy", "assisted")
    risk = definition["risk"]
    settings = db.get_settings()
    if settings.get("ai_dry_run") and risk != "read":
        return {"name": name, "success": False, "dry_run": True, "confirmation_required": True, "arguments": arguments}
    requires_confirmation = (
        risk == "destructive"
        or (risk == "consequential" and autonomy in ("suggestion", "assisted"))
        or (risk == "safe_write" and autonomy == "suggestion")
        or (risk == "destructive" and settings.get("ai_require_delete_confirmation", True))
    )
    if requires_confirmation and not confirmed:
        return {"name": name, "success": False, "confirmation_required": True, "arguments": arguments}
    if autonomy == "suggestion" and risk != "read":
        return {"name": name, "success": False, "confirmation_required": True, "arguments": arguments}

    key_material = json.dumps({"conversation_id": conversation_id, "name": name, "arguments": arguments}, sort_keys=True)
    idempotency_key = hashlib.sha256(key_material.encode()).hexdigest()
    existing = db.get_ai_operation_by_key(idempotency_key)
    if existing:
        return {"name": name, "success": existing["status"] == "success", "data": existing.get("result"), "replayed": True}
    try:
        data = _read_tool(name, arguments) if risk == "read" else _write_tool(name, arguments)
        db.create_ai_operation({
            "operation_type": name, "target_type": arguments.get("target_type"),
            "target_id": arguments.get("task_id") or arguments.get("project_id"),
            "arguments": arguments, "status": "success", "result": data,
            "idempotency_key": idempotency_key,
        })
        return {"name": name, "success": True, "data": data}
    except Exception as exc:
        db.create_ai_operation({
            "operation_type": name, "arguments": arguments, "status": "failed",
            "error_message": str(exc), "idempotency_key": idempotency_key,
        })
        return {"name": name, "success": False, "error": str(exc)}

