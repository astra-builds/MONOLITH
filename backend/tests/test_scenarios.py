import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from datetime import date, datetime, timedelta, timezone
from app.scheduler import schedule, split_sessions, estimate_completion, schedule_diff
from app import db
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_scenario_a_course_scheduling():
    """Scenario A: Course with 10 sessions, each 2 hours. Half session every Saturday.
    Expected: 20 one-hour study blocks on 20 consecutive Saturdays, strictly ordered.
    """
    settings = {
        "working_days": [0, 1, 2, 3, 4, 5],
        "working_start": "09:00",
        "working_end": "18:00",
        "max_daily_minutes": 480,
        "min_break_minutes": 15,
    }

    # Generate 20 tasks, 60 min each, preferred day Saturday (5), chained with dependencies
    tasks = []
    prev_id = None
    for i in range(20):
        tid = i + 1
        deps = [prev_id] if prev_id is not None else []
        tasks.append({
            "id": tid,
            "title": f"Course Session {i // 2 + 1}.{i % 2 + 1}",
            "remaining_minutes": 60,
            "estimated_minutes": 60,
            "priority": 3,
            "preferred_days": [5],  # Saturday
            "deadline": None,
            "dependencies": deps,
            "status": "todo",
            "splittable": False,
            "flexible": True,
            "min_session_minutes": 60,
            "max_session_minutes": 60,
            "preferred_start": None,
            "preferred_end": None,
            "project_id": 1,
        })
        prev_id = tid

    blocks, unscheduled = schedule(tasks, [], settings, [], projects=[{"id": 1, "kind": "course"}], horizon_days=200)

    assert len(unscheduled) == 0, f"Unscheduled tasks found: {unscheduled}"
    task_blocks = [b for b in blocks if b.get("task_id")]
    assert len(task_blocks) == 20

    # Verify each is on Saturday and strictly ordered in time
    saturdays = set()
    for i in range(len(task_blocks)):
        b = task_blocks[i]
        start_dt = datetime.fromisoformat(b["start_dt"])
        assert start_dt.weekday() == 5, f"Block {b['title']} scheduled on weekday {start_dt.weekday()}, expected 5 (Sat)"
        saturdays.add(start_dt.date())
        if i > 0:
            prev_b = task_blocks[i - 1]
            prev_start = datetime.fromisoformat(prev_b["start_dt"])
            assert start_dt > prev_start, f"Block {b['title']} not chronologically after {prev_b['title']}"

    # Exactly one block per distinct Saturday (cadence check — Scenario A requirement)
    assert len(saturdays) == 20, f"Expected 20 distinct Saturdays, got {len(saturdays)}"

    # Verify completion date calculation
    last_task = tasks[-1]
    est_comp = estimate_completion(last_task, task_blocks)
    assert est_comp is not None
    assert est_comp == task_blocks[-1]["end_dt"]


def test_scenario_b_weekly_commitments():
    """Scenario B: Fixed commitments (CS101, Math lab, Personal project, Academic study).
    Flexible work is fitted around commitments without overlap.
    """
    settings = {
        "working_days": [0, 1, 2, 3, 4, 5],
        "working_start": "09:00",
        "working_end": "18:00",
        "max_daily_minutes": 480,
        "min_break_minutes": 15,
    }

    commitments = [
        {
            "id": 101,
            "title": "University: CS101 Lecture",
            "kind": "fixed",
            "tag": "university",
            "recurrence": "weekly",
            "days_of_week": [2],  # Wednesday
            "start_time": "10:00",
            "end_time": "12:00",
        },
        {
            "id": 102,
            "title": "University: Math201 Lab",
            "kind": "fixed",
            "tag": "university",
            "recurrence": "weekly",
            "days_of_week": [3],  # Thursday
            "start_time": "14:00",
            "end_time": "16:00",
        },
    ]

    # Task with preferred day Wednesday (day 2)
    tasks = [
        {
            "id": 1,
            "title": "Homework",
            "remaining_minutes": 120,
            "estimated_minutes": 120,
            "priority": 2,
            "preferred_days": [2],
            "deadline": None,
            "dependencies": [],
            "status": "todo",
            "splittable": False,
            "flexible": True,
            "min_session_minutes": 120,
            "max_session_minutes": 120,
            "preferred_start": None,
            "preferred_end": None,
            "project_id": None,
        }
    ]

    blocks, unscheduled = schedule(tasks, commitments, settings, [], horizon_days=30)
    assert len(unscheduled) == 0

    hw_block = next(b for b in blocks if b.get("task_id") == 1)
    hw_start = datetime.fromisoformat(hw_block["start_dt"])
    hw_end = datetime.fromisoformat(hw_block["end_dt"])

    # If scheduled on Wednesday, check it does not overlap 10:00 - 12:00
    if hw_start.weekday() == 2:
        class_start = hw_start.replace(hour=10, minute=0, second=0)
        class_end = hw_start.replace(hour=12, minute=0, second=0)
        overlap = max(hw_start, class_start) < min(hw_end, class_end)
        assert not overlap, "Task overlapped with university lecture!"


def test_scenario_c_deadline_conflict():
    """Scenario C: Multiple tasks with overlapping deadlines and insufficient availability.
    Expected: Scheduler identifies conflict, does not overbook, and reports unscheduled with reasons.
    """
    settings = {
        "working_days": [0, 1, 2, 3, 4],  # Mon-Fri
        "working_start": "09:00",
        "working_end": "12:00",  # Only 3 hours per day!
        "max_daily_minutes": 180,
        "min_break_minutes": 15,
    }

    today = date.today()
    tomorrow = today + timedelta(days=1)

    # 4 tasks of 2 hours each = 8 hours total, but deadline is tomorrow, max working is 3h/day
    tasks = [
        {
            "id": i,
            "title": f"Urgent Task {i}",
            "remaining_minutes": 120,
            "estimated_minutes": 120,
            "priority": i,
            "preferred_days": [],
            "deadline": tomorrow.isoformat(),
            "dependencies": [],
            "status": "todo",
            "splittable": False,
            "flexible": True,
            "min_session_minutes": 120,
            "max_session_minutes": 120,
            "preferred_start": None,
            "preferred_end": None,
            "project_id": None,
        }
        for i in range(1, 5)
    ]

    blocks, unscheduled = schedule(tasks, [], settings, [], horizon_days=7)

    # Should not be able to fit all 8 hours into at most 2 days * 3 hours = 6 hours
    assert len(unscheduled) > 0, "Expected at least one task to be unscheduled due to conflict"
    for u in unscheduled:
        assert "Deadline" in u["reason"] or "available" in u["reason"]
        assert "Required" in u["reason"]


def test_scenario_d_missed_session_endpoint():
    """Scenario D: Missed session rescheduling via API.
    A scheduled session in the past is marked missed and rescheduled while preserving completed ones.
    """
    # Reset DB first
    db.reset_db()

    # Create project and task
    p = db.create_project({"name": "Test Course", "kind": "course"})
    t = db.create_task({
        "project_id": p["id"],
        "title": "Study Session",
        "estimated_minutes": 60,
        "remaining_minutes": 0,  # Scheduled completely
        "splittable": False,
    })

    # Create a scheduled block in the past
    past_start = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    past_end = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    db.create_block({
        "task_id": t["id"],
        "title": "Study Session",
        "start_dt": past_start,
        "end_dt": past_end,
        "status": "scheduled",
        "locked": False,
    })

    # Call /schedule/reschedule-missed
    res = client.post("/schedule/reschedule-missed")
    assert res.status_code == 200
    data = res.json()
    assert data["missed_count"] == 1
    assert data["missed_blocks"][0]["title"] == "Study Session"

    # Verify task remaining minutes were restored and rescheduled in future
    updated_t = db.get_task(t["id"])
    assert updated_t["remaining_minutes"] == 60


def test_scenario_e_changing_availability():
    """Scenario E: Make Wednesdays unavailable.
    Future flexible tasks recalculate off Wednesdays.
    """
    settings = {
        "working_days": [0, 1, 3, 4, 5],  # NO Wednesday (2)
        "working_start": "09:00",
        "working_end": "18:00",
        "max_daily_minutes": 480,
        "min_break_minutes": 15,
    }

    tasks = [
        {
            "id": 1,
            "title": "Flexible Task",
            "remaining_minutes": 180,
            "estimated_minutes": 180,
            "priority": 3,
            "preferred_days": [2],  # User prefers Wed, but Wed is unavailable!
            "deadline": None,
            "dependencies": [],
            "status": "todo",
            "splittable": True,
            "flexible": True,
            "min_session_minutes": 60,
            "max_session_minutes": 90,
            "preferred_start": None,
            "preferred_end": None,
            "project_id": None,
        }
    ]

    blocks, unscheduled = schedule(tasks, [], settings, [], horizon_days=30)
    task_blocks = [b for b in blocks if b.get("task_id")]
    assert len(task_blocks) > 0
    for b in task_blocks:
        st = datetime.fromisoformat(b["start_dt"])
        assert st.weekday() != 2, f"Task was scheduled on Wednesday despite Wednesday being unavailable!"


def test_scenario_f_persistence_and_endpoints():
    """Scenario F: Reset, seed demo, export, and import data to verify full persistence."""
    # 1. Reset
    res_reset = client.post("/demo/reset")
    assert res_reset.status_code == 200

    # 2. Seed
    res_seed = client.post("/demo/seed")
    assert res_seed.status_code == 200
    seed_data = res_seed.json()
    assert seed_data["tasks_created"] == 20
    assert seed_data["commitments_created"] == 4

    # 3. Export
    res_export = client.get("/export")
    assert res_export.status_code == 200
    export_data = res_export.json()
    assert len(export_data["projects"]) == 1
    assert len(export_data["tasks"]) == 20
    assert len(export_data["commitments"]) == 4

    # 4. Generate course sessions endpoint test
    res_proj = client.post("/projects", json={"name": "New Course", "kind": "course"})
    assert res_proj.status_code == 200
    new_pid = res_proj.json()["id"]

    res_gen = client.post(f"/projects/{new_pid}/generate-sessions", json={
        "title": "Machine Learning",
        "total_sessions": 5,
        "session_minutes": 120,
        "half": True,
        "day_of_week": 6,  # Sunday
    })
    assert res_gen.status_code == 200
    gen_data = res_gen.json()
    assert gen_data["sessions_created"] == 10

    # 5. Preview endpoint test
    res_preview = client.post("/schedule/preview")
    assert res_preview.status_code == 200
    preview_data = res_preview.json()
    assert "diff" in preview_data
    assert "new_blocks" in preview_data

    # 6. Import test
    res_import = client.post("/import", json=export_data)
    assert res_import.status_code == 200
    assert res_import.json()["imported"]["tasks"] == 20


def test_offline_natural_language_parser():
    """Phase 6: Verify offline deterministic natural language parser extracts
    courses with split sessions and routines from the prompt in instructions.txt.
    """
    input_text = "I have an Agentic AI course with 10 sessions. I want to complete half a session every Saturday. Mondays are for my personal project, and Tuesdays are for university work."
    res = client.post("/ai/extract", json={"text": input_text})
    assert res.status_code == 200
    data = res.json()
    assert "proposal" in data
    prop = data["proposal"]

    # Verify Course extracted
    assert len(prop["projects"]) == 1
    assert "Agentic AI" in prop["projects"][0]["name"]
    assert prop["projects"][0]["kind"] == "course"

    # Verify 20 half-session tasks generated
    assert len(prop["tasks"]) == 20
    assert prop["tasks"][0]["preferred_days"] == [5]  # Saturday

    # Verify routines extracted
    assert len(prop["commitments"]) >= 2
    monday_commit = next(c for c in prop["commitments"] if 0 in c["days_of_week"])
    tuesday_commit = next(c for c in prop["commitments"] if 1 in c["days_of_week"])
    assert monday_commit["tag"] == "personal"
    assert tuesday_commit["tag"] == "university"

    # Apply proposal and verify sequential dependencies are resolved
    db.reset_db()
    res_apply = client.post("/ai/apply", json=prop)
    assert res_apply.status_code == 200
    applied_data = res_apply.json()
    assert len(applied_data["tasks"]) == 20

    # Verify sequential dependencies resolved to real task IDs
    t2 = applied_data["tasks"][1]
    t1 = applied_data["tasks"][0]
    assert t2["dependencies"] == [t1["id"]]


# ---------------- Regression tests (Phase 4 Step 4.3) ----------------

def test_apply_no_duplication():
    """B2: Completing a block then applying twice must not duplicate blocks."""
    db.reset_db()
    p = db.create_project({"name": "Course", "kind": "course"})
    t = db.create_task({
        "project_id": p["id"],
        "title": "Session 1",
        "estimated_minutes": 60,
        "remaining_minutes": 60,
        "splittable": False,
        "preferred_days": [5],
        "status": "todo",
    })
    # Generate schedule
    client.post("/schedule/apply")
    blocks_after_first = db.list_blocks()
    task_blocks = [b for b in blocks_after_first if b.get("task_id") == t["id"]]
    assert len(task_blocks) == 1

    # Complete the task (marks its blocks completed)
    client.post(f"/tasks/{t['id']}/complete")

    # Apply twice
    client.post("/schedule/apply")
    client.post("/schedule/apply")

    blocks_after = db.list_blocks()
    task_blocks_after = [b for b in blocks_after if b.get("task_id") == t["id"]]
    assert len(task_blocks_after) == 1, f"Expected 1 block, got {len(task_blocks_after)}: {task_blocks_after}"


def test_pre_commitment_gap_usage():
    """G1: A free gap before a commitment can be filled."""
    db.reset_db()
    # A commitment at 10:00-11:00 on Monday; a task should fill 09:00-10:00
    settings = {
        "working_days": [0, 1, 2, 3, 4, 5],
        "working_start": "09:00",
        "working_end": "18:00",
        "max_daily_minutes": 480,
        "min_break_minutes": 15,
    }
    commitments = [{
        "id": 1, "title": "Class", "tag": "university",
        "recurrence": "weekly", "days_of_week": [0],
        "start_time": "10:00", "end_time": "11:00",
    }]
    tasks = [{
        "id": 1, "title": "Pre-class review",
        "remaining_minutes": 60, "priority": 1,
        "preferred_days": [0], "deadline": None,
        "dependencies": [], "status": "todo",
        "splittable": False, "flexible": True,
        "min_session_minutes": 60, "max_session_minutes": 60,
    }]
    # Find next Monday
    today = date.today()
    days_ahead = (0 - today.weekday()) % 7
    target_monday = today + timedelta(days=days_ahead)
    blocks, unscheduled = schedule(
        tasks, commitments, settings, [], horizon_days=days_ahead + 1,
    )
    task_blocks = [b for b in blocks if b.get("task_id") == 1]
    assert len(unscheduled) == 0, f"Task should be schedulable: {unscheduled}"
    assert len(task_blocks) == 1
    start = datetime.fromisoformat(task_blocks[0]["start_dt"])
    assert start.date() == target_monday
    assert start.hour == 9 and start.minute == 0, f"Expected 09:00, got {start.time()}"


def test_utc5_missed_marking():
    """R5/UTC: reschedule-missed compares naive-local, not UTC-aware now."""
    db.reset_db()
    p = db.create_project({"name": "Test", "kind": "course"})
    t = db.create_task({
        "project_id": p["id"],
        "title": "Study Session",
        "estimated_minutes": 60,
        "remaining_minutes": 0,
        "splittable": False,
    })
    # A block ending 3 hours ago (naive local)
    past_start = (datetime.now() - timedelta(hours=3)).isoformat()
    past_end = (datetime.now() - timedelta(hours=2)).isoformat()
    db.create_block({
        "task_id": t["id"], "title": "Study Session",
        "start_dt": past_start, "end_dt": past_end,
        "status": "scheduled", "locked": False,
    })
    res = client.post("/schedule/reschedule-missed")
    assert res.status_code == 200
    data = res.json()
    assert data["missed_count"] == 1
    updated_t = db.get_task(t["id"])
    assert updated_t["remaining_minutes"] == 60


def test_patch_null_clearing():
    """R1: PATCH with explicit null should clear deadline/target dates."""
    db.reset_db()
    # Create task with a deadline
    t = db.create_task({
        "title": "Task with deadline",
        "estimated_minutes": 60,
        "remaining_minutes": 60,
        "deadline": "2026-12-31",
        "status": "todo",
    })
    assert t["deadline"] == "2026-12-31"
    # Clear the deadline via PATCH null
    res = client.patch(f"/tasks/{t['id']}", json={"deadline": None})
    assert res.status_code == 200
    assert res.json()["deadline"] is None


def test_import_400_on_bad_payload():
    """R3: import_all with bad payload returns 400, not 500, and doesn't wipe first."""
    db.reset_db()
    # Seed something first
    db.create_project({"name": "Existing", "kind": "project"})
    assert len(db.list_projects()) == 1
    # Bad payload: missing required title in project
    bad = {"projects": [{"name": None}]}
    res = client.post("/import", json=bad)
    assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
    # Data should still be there (not wiped before validation)
    assert len(db.list_projects()) == 1


def test_skip_refund():
    """G4: Skip refunds block minutes back to the task."""
    db.reset_db()
    p = db.create_project({"name": "Course", "kind": "course"})
    t = db.create_task({
        "project_id": p["id"],
        "title": "Session 1",
        "estimated_minutes": 60,
        "remaining_minutes": 60,
        "splittable": False,
        "preferred_days": [5],
        "status": "todo",
    })
    client.post("/schedule/apply")
    task = db.get_task(t["id"])
    # Block created but remaining_minutes unchanged by scheduler
    assert task["remaining_minutes"] == 60
    # Skip the task → refund block minutes back
    client.post(f"/tasks/{t['id']}/skip")
    task = db.get_task(t["id"])
    assert task["remaining_minutes"] == 120, f"Expected refund to 120 min, got {task['remaining_minutes']}"


def test_move_locks_block():
    """R2: /move sets locked=True so next regen preserves it."""
    db.reset_db()
    p = db.create_project({"name": "Course", "kind": "course"})
    t = db.create_task({
        "project_id": p["id"],
        "title": "Session 1",
        "estimated_minutes": 60,
        "remaining_minutes": 60,
        "splittable": False,
        "preferred_days": [5],
        "status": "todo",
    })
    client.post("/schedule/apply")
    blocks = db.list_blocks()
    task_block = next(b for b in blocks if b.get("task_id") == t["id"])
    assert task_block["locked"] == 0

    # Move it
    new_start = "2026-11-07T14:00:00"
    new_end = "2026-11-07T15:00:00"
    res = client.post(
        f"/schedule/blocks/{task_block['id']}/move",
        params={"start_dt": new_start, "end_dt": new_end},
    )
    assert res.status_code == 200
    updated = res.json()
    assert updated["locked"] == 1
    assert updated["start_dt"] == new_start


def test_offline_parser_clarifications_list():
    """G7b: Offline parser returns clarifications as a consumable list."""
    db.reset_db()
    res = client.post("/ai/extract", json={"text": "course AI"})
    assert res.status_code == 200
    data = res.json()
    assert "proposal" in data
    assert "clarifications" in data["proposal"]
    assert isinstance(data["proposal"]["clarifications"], list)

