from fastapi import APIRouter, HTTPException
from typing import Optional
from .. import db
from ..models import CommitmentIn, CommitmentUpdate

router = APIRouter(prefix="/commitments", tags=["commitments"])

@router.get("")
def list_commitments(tag: Optional[str] = None):
    return db.list_commitments(tag=tag)

@router.post("")
def create_commitment(c: CommitmentIn):
    return db.create_commitment(c.model_dump())

@router.patch("/{cid}")
def update_commitment(cid: int, c: CommitmentUpdate):
    data = {k:v for k,v in c.model_dump().items() if v is not None}
    r = db.update_commitment(cid, data)
    if not r: raise HTTPException(404)
    # Regenerate so stale future blocks for this commitment are rebuilt at the
    # new time and flexible work is re-laid around them (G5).
    from ..routers.schedule import regenerate
    regenerate()
    return r

@router.delete("/{cid}")
def delete_commitment(cid: int):
    db.delete_commitment(cid)
    return {"ok": True}
