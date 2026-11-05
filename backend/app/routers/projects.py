import math

from fastapi import APIRouter, HTTPException
from .. import db
from ..models import ProjectIn, ProjectUpdate, CourseGenerateRequest

router = APIRouter(prefix="/projects", tags=["projects"])

@router.get("")
def list_projects():
    return db.list_projects()

@router.post("")
def create_project(p: ProjectIn):
    return db.create_project(p.model_dump())

@router.get("/{pid}")
def get_project(pid: int):
    p = db.get_project(pid)
    if not p: raise HTTPException(404)
    tasks = db.list_tasks(project_id=pid)
    blocks = [b for b in db.list_blocks() if b.get("task_id") in {t["id"] for t in tasks}]
    p["tasks"] = tasks
    p["blocks"] = blocks
    # progress
    total = len(tasks)
    done = sum(1 for t in tasks if t["status"]=="done")
    p["progress"] = (done/total*100) if total else 0
    p["completed"] = done
    p["remaining_tasks"] = total-done
    # estimated completion
    if blocks:
        p["estimated_completion"] = max(b["end_dt"] for b in blocks)
    else:
        p["estimated_completion"] = None
    return p

@router.patch("/{pid}")
def update_project(pid: int, p: ProjectUpdate):
    data = p.model_dump(exclude_unset=True)
    r = db.update_project(pid, data)
    if not r: raise HTTPException(404)
    return r

@router.delete("/{pid}")
def delete_project(pid: int):
    db.delete_project(pid)
    return {"ok": True}


@router.post("/{pid}/generate-sessions")
def generate_sessions(pid: int, req: CourseGenerateRequest):
    """Generate sequential course-session tasks for a project.

    If ``half`` is True, each logical session is split into two half-length
    blocks (e.g. "Session 01.1", "Session 01.2").  Otherwise each session maps
    to a single task block.

    If ``start_date`` is given, it is used as the anchor for the first task's
    start date.  Otherwise the current date is used.

    Every task depends on the previous one so the scheduler places them in
    sequential order.

    The endpoint is idempotent: prior tasks+blocks for this project are deleted
    before generating new ones.
    """
    project = db.get_project(pid)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Idempotent re-run: delete prior tasks and blocks for this project
    db.delete_project_tasks(pid)
    with db.connect() as conn:
        conn.execute("DELETE FROM schedule_blocks WHERE task_id IN (SELECT id FROM tasks WHERE project_id=?)", (pid,))

    if req.half:
        block_count = req.total_sessions * 2
        block_minutes = req.session_minutes // 2
    else:
        block_count = req.total_sessions
        block_minutes = req.session_minutes

    created_tasks = []
    prev_task_id: int | None = None

    for i in range(block_count):
        if req.half:
            session_num = i // 2 + 1
            sub = i % 2 + 1  # 1 or 2
            title = f"{req.title} - Session {session_num:02d}.{sub}"
        else:
            title = f"{req.title} - Session {i + 1:02d}"

        deps: list[int] = [prev_task_id] if prev_task_id is not None else []

        # Anchor the first session to start_date. Drop the per-task deadline
        # stamp; apply the project deadline only to the last session.
        task_deadline = None
        if i == 0 and req.start_date:
            task_deadline = req.start_date
        elif i == block_count - 1 and req.deadline:
            task_deadline = req.deadline

        task_data = {
            "project_id": pid,
            "title": title,
            "description": "",
            "estimated_minutes": block_minutes,
            "remaining_minutes": block_minutes,
            "deadline": task_deadline,
            "priority": 3,
            "preferred_days": [req.day_of_week],
            "preferred_start": None,
            "preferred_end": None,
            "min_session_minutes": block_minutes,
            "max_session_minutes": block_minutes,
            "splittable": False,
            "flexible": True,
            "dependencies": deps,
            "status": "todo",
        }
        task = db.create_task(task_data)
        created_tasks.append(task)
        prev_task_id = task["id"]

    # Update project metadata
    db.update_project(pid, {
        "total_sessions": req.total_sessions,
        "session_minutes": req.session_minutes,
    })

    # When splitting into half-sessions, two blocks land per week.
    sessions_per_week = 2 if req.half else 1
    estimated_weeks = math.ceil(block_count / sessions_per_week)

    return {
        "project_id": pid,
        "sessions_created": block_count,
        "tasks": created_tasks,
        "estimated_weeks": estimated_weeks,
    }
