"""Build the authoritative application context supplied to the planner."""

from .. import db


def get_planning_context(conversation_id: str | None = None) -> dict:
    """Read current state in one stable shape for prompts and tool execution."""
    settings = db.get_settings()
    # Provider credentials are application secrets, never planning context.
    settings = {key: value for key, value in settings.items() if key != "ai_api_key"}
    return {
        "settings": settings,
        "projects": db.list_projects(),
        "milestones": db.list_milestones(),
        "tasks": db.list_tasks(),
        "commitments": db.list_commitments(),
        "schedule_blocks": db.list_blocks(),
        "availability_rules": db.list_availability_rules(),
        "conversation": db.get_conversation(conversation_id) if conversation_id else None,
    }

