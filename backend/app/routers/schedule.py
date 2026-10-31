from fastapi import APIRouter, HTTPException
from datetime import date, datetime, timedelta, timezone
from .. import db
from ..models import BlockUpdate
from ..scheduler import schedule as run_schedule, parse_dt

router = APIRouter(prefix="/schedule", tags=["schedule"])

def _gen(preview=True, apply=False):
    settings = db.get_settings()
    tasks = db.list_tasks()
    commitments = db.list_commitments()
    projects = db.list_projects()
    existing = db.list_blocks()
    # preserve locked/completed/past
    # filter existing blocks to preserve
    preserved = []
    from datetime import datetime
    today = date.today()
    for b in existing:
        sd = parse_dt(b["start_dt"])
        if b.get("locked") or b.get("status") in ("completed","skipped") or (sd and sd.date() < today):
            preserved.append(b)
    # remove flexible future blocks if applying
    new_blocks, unscheduled = run_schedule(tasks, commitments, settings, preserved, projects, horizon_days=180)
    # For preview, don't persist. For apply, replace future flexible blocks.
    if apply:
        # delete future flexible scheduled blocks
        db.delete_future_flexible_blocks(datetime.now().isoformat())
        # delete all future non-locked? We'll just clear scheduled flexible already handled.
        # insert new flexible blocks (locked ones from preserved? preserved locked already in db; but new_blocks includes locked fixed intervals too -> would duplicate)
        # To avoid duplicates: only insert blocks that are not already in preserved locked.
        existing_ids = {(b["start_dt"], b["title"]) for b in preserved if b.get("locked")}
        for nb in new_blocks:
            if nb.get("locked"):
                # skip if already present
                if (nb["start_dt"], nb["title"]) in existing_ids:
                    continue
            db.create_block(nb)
        # update task remaining? leave.
    return {"blocks": new_blocks, "unscheduled": unscheduled, "preserved": [b["id"] for b in preserved]}

@router.get("")
def list_blocks(start: str = None, end: str = None):
    return db.list_blocks(start=start, end=end)

@router.post("/generate")
def generate(preview: bool = True):
    return _gen(preview=True, apply=not preview)

@router.post("/apply")
def apply_schedule():
    return _gen(preview=False, apply=True)

@router.post("/regenerate")
def regenerate():
    return _gen(preview=False, apply=True)

@router.patch("/blocks/{bid}")
def update_block(bid: int, u: BlockUpdate):
    data = {k:v for k,v in u.model_dump().items() if v is not None}
    if "start_dt" in data or "end_dt" in data:
        data["locked"] = True
    r = db.update_block(bid, data)
    if not r: raise HTTPException(404)
    return r

@router.delete("/blocks/{bid}")
def delete_block(bid: int):
    db.delete_block(bid)
    return {"ok": True}

@router.post("/blocks/{bid}/move")
def move_block(bid: int, start_dt: str, end_dt: str):
    r = db.update_block(bid, {"start_dt": start_dt, "end_dt": end_dt})
    if not r: raise HTTPException(404)
    return r


# ---- Reschedule missed blocks ------------------------------------------------

@router.post("/reschedule-missed")
def reschedule_missed():
    """Find past scheduled (non-locked) blocks, mark them missed,
    restore their duration to the parent task, then regenerate the schedule.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    all_blocks = db.list_blocks()

    missed_blocks: list[dict] = []
    for b in all_blocks:
        if (
            b.get("status") == "scheduled"
            and b.get("end_dt", "") < now_iso
            and not b.get("locked")
        ):
            # Mark block as missed
            db.update_block(b["id"], {"status": "missed"})
            missed_blocks.append(b)

            # Restore duration to parent task
            if b.get("task_id"):
                task = db.get_task(b["task_id"])
                if task:
                    start = parse_dt(b["start_dt"])
                    end = parse_dt(b["end_dt"])
                    block_minutes = int((end - start).total_seconds() / 60)
                    new_remaining = (task.get("remaining_minutes") or 0) + block_minutes
                    db.update_task(b["task_id"], {"remaining_minutes": new_remaining})

    # Regenerate the schedule
    regen = _gen(preview=False, apply=True)

    return {
        "missed_count": len(missed_blocks),
        "missed_blocks": missed_blocks,
        "schedule": regen,
    }


# ---- Schedule preview with diff ----------------------------------------------

@router.post("/preview")
def preview_diff():
    """Generate a new schedule without applying it and produce a diff
    against the current schedule.
    """
    current_blocks = db.list_blocks()

    # Run scheduler in preview mode (do not persist)
    gen_result = _gen(preview=True, apply=False)
    new_blocks: list[dict] = gen_result.get("blocks", [])
    unscheduled: list[dict] = gen_result.get("unscheduled", [])

    # Build lookup maps
    # Key by task_id for comparison (skip commitment-only blocks)
    current_by_task: dict[int, list[dict]] = {}
    for b in current_blocks:
        tid = b.get("task_id")
        if tid is not None:
            current_by_task.setdefault(tid, []).append(b)

    new_by_task: dict[int, list[dict]] = {}
    for b in new_blocks:
        tid = b.get("task_id")
        if tid is not None:
            new_by_task.setdefault(tid, []).append(b)

    created: list[dict] = []
    moved: list[dict] = []
    removed: list[dict] = []
    unchanged: list[dict] = []

    # Current task IDs & new task IDs
    current_task_ids = set(current_by_task.keys())
    new_task_ids = set(new_by_task.keys())

    # Created: task blocks in new but not in current
    for tid in new_task_ids - current_task_ids:
        created.extend(new_by_task[tid])

    # Removed: flexible current blocks not present in new
    for tid in current_task_ids - new_task_ids:
        for b in current_by_task[tid]:
            if not b.get("locked"):
                removed.append(b)

    # Moved / unchanged: tasks present in both
    for tid in current_task_ids & new_task_ids:
        cur_set = {(b["start_dt"], b["end_dt"]) for b in current_by_task[tid]}
        new_set = {(b.get("start_dt"), b.get("end_dt")) for b in new_by_task[tid]}

        for b in new_by_task[tid]:
            key = (b.get("start_dt"), b.get("end_dt"))
            if key in cur_set:
                unchanged.append(b)
            else:
                moved.append(b)

    diff = {
        "created": created,
        "moved": moved,
        "removed": removed,
        "unchanged": unchanged,
        "unscheduled": unscheduled,
    }

    return {
        "diff": diff,
        "new_blocks": new_blocks,
        "unscheduled": unscheduled,
    }
