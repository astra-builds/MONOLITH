from fastapi import APIRouter
from .. import db
from ..models import SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("")
def get_settings():
    data = db.get_settings()
    # Never leak the AI API key to the client (instructions.txt:265).
    key = data.get("ai_api_key", "")
    data["ai_api_key"] = "********" if key else ""
    return data

@router.patch("")
def update_settings(s: SettingsUpdate):
    cur = db.get_settings()
    data = s.model_dump(exclude_unset=True)
    # The settings GET endpoint masks ai_api_key as "********" for display.
    # Persisting that mask would destroy the real key, so never clobber it.
    if data.get("ai_api_key") == "********":
        data.pop("ai_api_key", None)
    cur.update(data)
    db.save_settings(cur)
    return cur
