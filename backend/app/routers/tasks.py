from fastapi import APIRouter, HTTPException
from .. import db
from ..models import TaskIn, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.get("")
def list_tasks(project_id: int = None, status: str = None):
    return db.list_tasks(project_id=project_id, status=status)

@router.post("")
def create_task(t: TaskIn):
    data = t.model_dump()
    if data.get("remaining_minutes") is None:
        data["remaining_minutes"] = data["estimated_minutes"]
    return db.create_task(data)

@router.get("/{tid}")
def get_task(tid: int):
    t = db.get_task(tid)
    if not t: raise HTTPException(404)
    return t

@router.patch("/{tid}")
def update_task(tid: int, t: TaskUpdate):
    data = {k:v for k,v in t.model_dump().items() if v is not None}
    r = db.update_task(tid, data)
    if not r: raise HTTPException(404)
    return r

@router.delete("/{tid}")
def delete_task(tid: int):
    db.delete_task(tid)
    return {"ok": True}

@router.post("/{tid}/complete")
def complete_task(tid: int):
    t = db.get_task(tid)
    if not t: raise HTTPException(404)
    # mark done, remaining 0
    db.update_task(tid, {"status":"done","remaining_minutes":0,"completed_at": db.now_iso()})
    # mark its future blocks completed? mark scheduled blocks for this task as completed
    for b in db.list_blocks():
        if b["task_id"]==tid and b["status"]=="scheduled":
            db.update_block(b["id"], {"status":"completed"})
    return db.get_task(tid)

@router.post("/{tid}/skip")
def skip_task(tid: int):
    t = db.get_task(tid)
    if not t: raise HTTPException(404)
    # mark missed scheduled blocks skipped
    for b in db.list_blocks():
        if b["task_id"]==tid and b["status"]=="scheduled":
            db.update_block(b["id"], {"status":"skipped"})
    return db.get_task(tid)
