"""Demo / seed data endpoints for MONOLITH.

Provides quick seed and reset operations for development and testing.
"""

from fastapi import APIRouter
from .. import db
from ..models import ImportRequest

router = APIRouter(tags=["demo"])


# ---- Seed demo data ----------------------------------------------------------

@router.post("/demo/seed")
def seed_demo_data():
    """Populate the database with two demo scenarios.

    **Scenario A** — *Agentic AI Course*: a course project with 10 sessions
    (each 120 min), split into 20 half-session tasks (60 min) scheduled every
    Saturday with sequential dependencies.

    **Scenario B** — *Fixed commitments*: four weekly time-blocks representing
    typical university and personal obligations.
    """

    # ------------------------------------------------------------------
    # Scenario A: Course project
    # ------------------------------------------------------------------
    course_project = db.create_project({
        "name": "Agentic AI Course",
        "description": "Online course on Agentic AI — 10 sessions",
        "kind": "course",
        "total_sessions": 10,
        "session_minutes": 120,
        "target_deadline": None,
    })
    pid = course_project["id"]

    total_sessions = 10
    session_minutes = 120
    half = True

    if half:
        block_count = total_sessions * 2  # 20
        block_minutes = session_minutes // 2  # 60
    else:
        block_count = total_sessions
        block_minutes = session_minutes

    created_tasks = []
    prev_task_id = None

    for i in range(block_count):
        if half:
            session_num = i // 2 + 1
            sub = i % 2 + 1
            title = f"Agentic AI Course - Session {session_num:02d}.{sub}"
        else:
            title = f"Agentic AI Course - Session {i + 1:02d}"

        deps = [prev_task_id] if prev_task_id is not None else []

        task = db.create_task({
            "project_id": pid,
            "title": title,
            "description": "",
            "estimated_minutes": block_minutes,
            "remaining_minutes": block_minutes,
            "deadline": None,
            "priority": 3,
            "preferred_days": [5],  # Saturday
            "preferred_start": None,
            "preferred_end": None,
            "min_session_minutes": block_minutes,
            "max_session_minutes": block_minutes,
            "splittable": False,
            "flexible": True,
            "dependencies": deps,
            "status": "todo",
        })
        created_tasks.append(task)
        prev_task_id = task["id"]

    # ------------------------------------------------------------------
    # Scenario B: Fixed commitments
    # ------------------------------------------------------------------
    commitments_spec = [
        {
            "title": "University: CS101 Lecture",
            "kind": "fixed",
            "tag": "university",
            "recurrence": "weekly",
            "days_of_week": [2],  # Wednesday
            "start_time": "10:00",
            "end_time": "12:00",
        },
        {
            "title": "University: Math201 Lab",
            "kind": "fixed",
            "tag": "university",
            "recurrence": "weekly",
            "days_of_week": [3],  # Thursday
            "start_time": "14:00",
            "end_time": "16:00",
        },
        {
            "title": "Personal Project Time",
            "kind": "fixed",
            "tag": "personal",
            "recurrence": "weekly",
            "days_of_week": [0],  # Monday
            "start_time": "09:00",
            "end_time": "13:00",
        },
        {
            "title": "Academic Study",
            "kind": "fixed",
            "tag": "university",
            "recurrence": "weekly",
            "days_of_week": [1],  # Tuesday
            "start_time": "09:00",
            "end_time": "13:00",
        },
    ]

    created_commitments = []
    for spec in commitments_spec:
        c = db.create_commitment(spec)
        created_commitments.append(c)

    return {
        "ok": True,
        "project": course_project,
        "tasks_created": len(created_tasks),
        "commitments_created": len(created_commitments),
    }


# ---- Reset everything --------------------------------------------------------

@router.post("/demo/reset")
def reset_demo():
    """Delete **all** data from every table and reinitialize settings to
    their defaults.  This is destructive — use with care.
    """
    db.reset_db()
    return {"ok": True, "message": "Database reset complete"}


# ---- Import data (mirrors /export) -------------------------------------------

@router.post("/import")
def import_data(payload: ImportRequest):
    """Import a previously exported JSON snapshot.

    Clears all existing data, then inserts settings, projects, tasks,
    commitments, and schedule_blocks in FK-safe order.
    """
    counts = db.import_all(payload.model_dump())
    return {"ok": True, "imported": counts}
