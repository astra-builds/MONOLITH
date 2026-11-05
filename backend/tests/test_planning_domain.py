import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest  # noqa: E402

from app import db
from app.ai.context import get_planning_context
from app.ai.schemas import CommitmentIntent, TaskIntent
from app.ai.service import plan_request
from app.ai.tools import execute_tool


def test_planning_domain_tables_and_records():
    db.init_db()
    project = db.create_project({"name": "Planning domain"})
    milestone = db.create_milestone({
        "project_id": project["id"],
        "title": "First checkpoint",
        "deadline": "2026-11-10",
    })
    proposal = db.create_planning_proposal({
        "request_text": "Plan my project",
        "source": "offline",
        "structured_plan": {"projects": [{"name": "Planning domain"}]},
    })
    operation = db.create_ai_operation({
        "proposal_id": proposal["id"],
        "operation_type": "preview_schedule",
        "arguments": {"proposal_id": proposal["id"]},
        "idempotency_key": "test-preview-1",
    })

    assert db.get_milestone(milestone["id"])["project_id"] == project["id"]
    assert db.get_planning_proposal(proposal["id"])["structured_plan"]["projects"]
    assert operation["arguments"]["proposal_id"] == proposal["id"]


def test_task_intent_rejects_invalid_weekday_and_session_range():
    with pytest.raises(ValueError):
        TaskIntent(title="Bad day", preferred_days=[7])
    with pytest.raises(ValueError):
        TaskIntent(title="Bad range", min_session_minutes=90, max_session_minutes=30)


def test_commitment_intent_requires_valid_recurrence():
    with pytest.raises(ValueError):
        CommitmentIntent(
            title="Missing weekday",
            recurrence="weekly",
            start_time="09:00",
            end_time="10:00",
        )


def test_plan_request_persists_preview_without_mutating_workspace():
    db.reset_db()
    db.save_settings({**db.get_settings(), "ai_api_key": "secret-value"})
    result = plan_request("Add task Read the planning notes for 30 minutes")

    assert result["proposal_id"] > 0
    assert result["source"] == "offline"
    assert result["proposal"]["intent"]["tasks"][0]["title"]
    assert result["proposal"]["intent"]["tasks"][0]["estimated_minutes"] == 30
    assert db.list_projects() == []
    assert db.list_tasks() == []
    assert db.list_commitments() == []
    assert "ai_api_key" not in get_planning_context()["settings"]


def test_tools_enforce_autonomy_and_are_idempotent():
    db.reset_db()
    task = db.create_task({"title": "Read notes", "estimated_minutes": 30})

    skipped = execute_tool("skip_task", {"task_id": task["id"]}, conversation_id="test")
    assert skipped["confirmation_required"] is True

    completed = execute_tool("complete_task", {"task_id": task["id"]}, conversation_id="test")
    replayed = execute_tool("complete_task", {"task_id": task["id"]}, conversation_id="test")
    assert completed["success"] is True
    assert replayed["replayed"] is True
    assert db.get_task(task["id"])["status"] == "done"


def test_conversation_resolves_task_reference():
    db.reset_db()
    task = db.create_task({"title": "Lecture 03", "estimated_minutes": 30})
    from app.ai.service import handle_conversation_message

    response = handle_conversation_message("conversation-1", "I completed Lecture 03")
    assert response["type"] == "tool_result"
    assert response["tool"]["success"] is True
    assert db.get_task(task["id"])["status"] == "done"
    with pytest.raises(ValueError):
        CommitmentIntent(
            title="Missing date",
            recurrence="once",
            start_time="09:00",
            end_time="10:00",
        )

