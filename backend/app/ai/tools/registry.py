"""Validated application tools available to the AI operator."""

import hashlib
import json
from datetime import datetime

from ... import db
from ...scheduler import parse_dt


TOOL_DEFINITIONS = {
    "get_calendar_events": {"description": "Read schedule blocks", "risk": "read"},
    "get_projects": {"description": "Read projects and milestones", "risk": "read"},
    "get_tasks": {"description": "Read tasks", "risk": "read"},
    "get_commitments": {"description": "Read fixed and recurring commitments", "risk": "read"},
    "get_project_progress": {"description": "Read project progress and completion estimate", "risk": "read"},
    "inspect_scheduling_conflicts": {"description": "Read unscheduled/conflicting work", "risk": "read"},
    "preview_schedule": {"description": "Generate a deterministic proposal schedule preview", "risk": "read"},
    "create_project": {"description": "Create a project", "risk": "consequential"},
    "update_project": {"description": "Update a project", "risk": "consequential"},
    "create_task": {"description": "Create a task", "risk": "consequential"},
    "update_task": {"description": "Update a task", "risk": "consequential"},
    "delete_task": {"description": "Delete a task", "risk": "destructive"},
    "create_commitment": {"description": "Create a recurring commitment", "risk": "consequential"},
    "update_commitment": {"description": "Update a recurring commitment", "risk": "consequential"},
    "complete_task": {"description": "Mark a task complete", "risk": "safe_write"},
    "skip_task": {"description": "Skip a task and refund scheduled time", "risk": "consequential"},
    "update_availability": {"description": "Add an availability rule", "risk": "consequential"},
}


def _read_tool(name, args):
    if name == "get_calendar_events":
        return db.list_blocks(args.get("start"), args.get("end"))
    if name == "get_projects":
        return db.list_projects()
    if name == "get_tasks":
        return db.list_tasks(args.get("project_id"), args.get("status"))
    if name == "get_commitments":
        return db.list_commitments(args.get("tag"))
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
        return {"unscheduled": [], "message": "Use a proposal preview for a fresh deterministic conflict analysis."}
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
    requires_confirmation = risk in ("consequential", "destructive") or (risk == "safe_write" and autonomy == "suggestion")
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

