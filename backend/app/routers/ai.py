from fastapi import APIRouter, HTTPException
from ..models import AIPlanRequest
from ..ai import service

router = APIRouter(prefix="/ai", tags=["ai"])

@router.post("/extract")
def extract(req: AIPlanRequest):
    return service.extract_and_preview(req.text)

@router.post("/apply")
def apply_proposal(proposal: dict):
    return service.apply_proposal(proposal)

@router.post("/chat")
def chat(req: AIPlanRequest):
    p = service.get_provider()
    if p is None or not p.is_configured():
        return {"configured": False, "message": "AI not configured."}
    return {"configured": True, "reply": p.chat(req.text)}
