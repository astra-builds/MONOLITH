from fastapi import APIRouter
from .. import db
from ..models import SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("")
def get_settings():
    return db.get_settings()

@router.patch("")
def update_settings(s: SettingsUpdate):
    cur = db.get_settings()
    data = {k:v for k,v in s.model_dump().items() if v is not None}
    cur.update(data)
    db.save_settings(cur)
    return cur
