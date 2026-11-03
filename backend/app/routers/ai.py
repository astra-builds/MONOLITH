from fastapi import APIRouter, HTTPException
from .. import db
from ..models import AIPlanRequest, AIConversationMessage
from ..ai import service
from ..ai.tools import TOOL_DEFINITIONS, execute_tool

router = APIRouter(prefix="/ai", tags=["ai"])

@router.post("/extract")
def extract(req: AIPlanRequest):
    return service.extract_and_preview(req.text)

@router.post("/plan")
def plan(req: AIPlanRequest):
    try:
        return service.plan_request(req.text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: int):
    proposal = db.get_planning_proposal(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Planning proposal not found")
    return proposal

@router.post("/proposals/{proposal_id}/preview")
def preview_proposal(proposal_id: int):
    try:
        return service.preview_proposal(proposal_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: int):
    try:
        return service.approve_proposal(proposal_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: int):
    proposal = db.update_planning_proposal(proposal_id, {"status": "rejected"})
    if not proposal:
        raise HTTPException(status_code=404, detail="Planning proposal not found")
    return proposal

@router.post("/apply")
def apply_proposal(proposal: dict):
    return service.apply_proposal(proposal)

@router.post("/chat")
def chat(req: AIPlanRequest):
    p = service.get_provider()
    if p is None or not p.is_configured():
        return {"configured": False, "message": "AI not configured."}
    return {"configured": True, "reply": p.chat(req.text)}

@router.get("/provider")
def provider_status():
    p = service.get_provider()
    if p is None or not p.is_configured():
        return {"configured": False, "provider": "none", "capabilities": {}}
    return {"configured": True, "provider": p.__class__.__name__, "model": p.model, "capabilities": p.capabilities()}

@router.post("/recalculate")
def recalculate():
    from .schedule import regenerate
    return {"source": "adaptive_event", "schedule": regenerate()}

@router.post("/conversations/{conversation_id}/messages")
def conversation_message(conversation_id: str, req: AIConversationMessage):
    try:
        return service.handle_conversation_message(conversation_id, req.text, req.confirm)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.get("/tools")
def list_tools():
    return TOOL_DEFINITIONS

@router.post("/tools/execute")
def run_tool(payload: dict):
    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=422, detail="Tool name is required")
    return execute_tool(
        name,
        payload.get("arguments", {}),
        confirmed=bool(payload.get("confirmed", False)),
        conversation_id=payload.get("conversation_id"),
    )
