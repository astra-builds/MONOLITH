import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.scheduler import schedule, split_sessions, topo_sort, schedule_diff
from datetime import date, datetime, timedelta

def test_split():
    # Splittable
    assert split_sessions({"remaining_minutes": 120, "min_session_minutes": 25, "max_session_minutes": 60, "splittable": True}) == [60, 60]
    assert split_sessions({"remaining_minutes": 60, "min_session_minutes": 25, "max_session_minutes": 90, "splittable": True}) == [60]
    # Non-splittable (Rule 7)
    assert split_sessions({"remaining_minutes": 180, "min_session_minutes": 25, "max_session_minutes": 60, "splittable": False}) == [180]
    # Remaining zero
    assert split_sessions({"remaining_minutes": 0, "splittable": True}) == []

def test_basic():
    tasks = [{"id":1,"title":"Study","remaining_minutes":120,"priority":3,"preferred_days":[5],"deadline":None,"dependencies":[],"status":"todo","flexible":1,"min_session_minutes":25,"max_session_minutes":60,"preferred_start":None,"preferred_end":None,"project_id":None}]
    settings = {"working_days":[0,1,2,3,4,5],"working_start":"09:00","working_end":"18:00","max_daily_minutes":480,"min_break_minutes":15}
    blocks, unsched = schedule(tasks, [], settings, [], None, 60)
    assert len(blocks) == 2
    assert unsched == []

def test_break_enforcement():
    """Rule 9: Enforce minimum break between consecutive sessions on same day."""
    tasks = [
        {"id": 1, "title": "Session 1", "remaining_minutes": 60, "priority": 1, "dependencies": [], "status": "todo", "splittable": False, "flexible": True},
        {"id": 2, "title": "Session 2", "remaining_minutes": 60, "priority": 2, "dependencies": [1], "status": "todo", "splittable": False, "flexible": True},
    ]
    settings = {"working_days": [0,1,2,3,4,5], "working_start": "09:00", "working_end": "18:00", "max_daily_minutes": 480, "min_break_minutes": 15}
    blocks, unsched = schedule(tasks, [], settings, [], None, 10)
    assert len(unsched) == 0
    t1_block = next(b for b in blocks if b.get("task_id") == 1)
    t2_block = next(b for b in blocks if b.get("task_id") == 2)
    t1_end = datetime.fromisoformat(t1_block["end_dt"])
    t2_start = datetime.fromisoformat(t2_block["start_dt"])
    # If scheduled on the same day, gap must be >= 15 min
    if t1_end.date() == t2_start.date():
        gap_min = int((t2_start - t1_end).total_seconds() / 60)
        assert gap_min >= 15, f"Expected at least 15 min break, got {gap_min} min"

def test_topo_sort_priority_deadline():
    """Rule 4: Topo sort prioritizes earlier deadlines and higher priority (lower number)."""
    tasks = [
        {"id": 1, "title": "No Deadline Low Prio", "priority": 5, "deadline": None, "dependencies": []},
        {"id": 2, "title": "Early Deadline", "priority": 3, "deadline": "2026-11-01", "dependencies": []},
        {"id": 3, "title": "Urgent High Prio", "priority": 1, "deadline": "2026-11-05", "dependencies": []},
        {"id": 4, "title": "Dependent on 2", "priority": 1, "deadline": "2026-10-31", "dependencies": [2]},
    ]
    sorted_tasks = topo_sort(tasks)
    ids = [t["id"] for t in sorted_tasks]
    # Task 2 must precede Task 4 due to dependency
    assert ids.index(2) < ids.index(4)
    # Among independent tasks (1, 2, 3), task 2 (earlier deadline) comes before task 3 (later deadline), which comes before task 1 (no deadline)
    assert ids.index(2) < ids.index(1)
    assert ids.index(3) < ids.index(1)

def test_schedule_diff():
    old_blocks = [
        {"task_id": 1, "commitment_id": None, "title": "Task A", "start_dt": "2026-11-01T09:00:00", "end_dt": "2026-11-01T10:00:00"},
        {"task_id": 2, "commitment_id": None, "title": "Task B", "start_dt": "2026-11-01T10:00:00", "end_dt": "2026-11-01T11:00:00"},
    ]
    new_blocks = [
        {"task_id": 1, "commitment_id": None, "title": "Task A", "start_dt": "2026-11-01T09:00:00", "end_dt": "2026-11-01T10:00:00"},  # Unchanged
        {"task_id": 2, "commitment_id": None, "title": "Task B", "start_dt": "2026-11-01T11:00:00", "end_dt": "2026-11-01T12:00:00"},  # Moved
        {"task_id": 3, "commitment_id": None, "title": "Task C", "start_dt": "2026-11-01T13:00:00", "end_dt": "2026-11-01T14:00:00"},  # Created
    ]
    diff = schedule_diff(old_blocks, new_blocks)
    assert len(diff["unchanged"]) == 1
    assert len(diff["moved"]) == 1
    assert len(diff["created"]) == 1
    assert len(diff["removed"]) == 0
