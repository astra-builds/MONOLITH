"""Golden fixtures for Phases 0-2: contracts and state-aware operator runs."""
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import db
from app.ai import service
from app.ai.gemini import GeminiProvider
from app.scheduler import schedule


def _configure_gemini():
    db.reset_db()
    db.save_settings({**db.get_settings(), "ai_provider": "gemini", "ai_api_key": "test-key", "ai_model": "test-model"})


def test_provider_tool_contracts_are_typed():
    from app.ai.tools.registry import tool_schemas

    names = {item["function"]["name"] for item in tool_schemas()}
    read_names = {item["function"]["name"] for item in tool_schemas(read_only=True)}
    assert "get_commitments" in names
    assert "update_commitment" in names
    assert "update_commitment" not in read_names
    commitment = next(item for item in tool_schemas() if item["function"]["name"] == "update_commitment")
    assert "commitment_id" in commitment["function"]["parameters"]["required"]


def test_operator_inspects_monday_and_drafts_targeted_rename(monkeypatch):
    _configure_gemini()
    commitment = db.create_commitment({
        "title": "Agentic AI", "tag": "course", "recurrence": "weekly",
        "days_of_week": [0], "start_time": "17:00", "end_time": "18:00",
    })
    calls = []

    def fake_turn(self, messages, tools=None):
        calls.append(messages[-1])
        if len(calls) == 1:
            return {"content": "", "tool_calls": [{"id": "1", "name": "get_commitments", "arguments": {"weekday": 0, "query": "course"}}]}
        return {"content": json.dumps({
            "summary": "Rename the Monday course",
            "operations": [{"operation": "update", "entity_type": "commitment", "target_id": commitment["id"], "fields": {"title": "University Agentic AI"}, "reason": "Matched the Monday course."}],
            "clarifications": [], "assumptions": [], "tasks": [], "projects": [], "commitments": [],
        }), "tool_calls": []}

    monkeypatch.setattr(GeminiProvider, "chat_turn", fake_turn)
    result = service.operator_request("Rename the courses on Mondays")

    assert result["proposal"]["intent"]["operations"][0]["target_id"] == commitment["id"]
    assert result["proposal"]["intent"]["operations"][0]["fields"]["title"] == "University Agentic AI"
    assert len(result["operator"]["tool_events"]) == 1
    # Phase 2 drafts; it does not silently mutate application state.
    assert db.get_commitment(commitment["id"])["title"] == "Agentic AI"


def test_operator_represents_bounded_routine_and_deadline(monkeypatch):
    _configure_gemini()

    def fake_turn(self, messages, tools=None):
        return {"content": json.dumps({
            "summary": "Bound the routine and add the capstone deadline",
            "operations": [
                {"operation": "create", "entity_type": "commitment", "fields": {
                    "title": "Agentic AI study", "recurrence": "weekly", "days_of_week": [0],
                    "start_time": "17:00", "end_time": "18:00", "tag": "course",
                    "start_date": "2026-11-09", "end_date": "2027-02-03",
                }, "reason": "The routine is explicitly bounded."},
                {"operation": "create", "entity_type": "milestone", "fields": {
                    "title": "Capstone project", "deadline": "2027-02-07",
                }, "reason": "The user supplied a capstone deadline."},
            ],
            "clarifications": [], "assumptions": [], "tasks": [], "projects": [], "commitments": [],
        }), "tool_calls": []}

    monkeypatch.setattr(GeminiProvider, "chat_turn", fake_turn)
    result = service.operator_request("Follow this routine until 3 February and add my capstone deadline on 7 February")
    operations = result["proposal"]["intent"]["operations"]
    assert operations[0]["fields"]["end_date"] == "2027-02-03"
    assert operations[1]["fields"]["deadline"] == "2027-02-07"
    assert db.list_commitments() == []
    assert db.list_milestones() == []


def test_operator_stops_after_bounded_tool_turns(monkeypatch):
    _configure_gemini()

    def fake_turn(self, messages, tools=None):
        return {"content": "", "tool_calls": [{"id": "loop", "name": "get_tasks", "arguments": {}}]}

    monkeypatch.setattr(GeminiProvider, "chat_turn", fake_turn)
    try:
        service.operator_request("Keep inspecting forever")
    except ValueError as exc:
        assert "maximum" in str(exc)
    else:
        raise AssertionError("operator must stop after its maximum turn count")


def test_semantic_resolution_returns_candidates_and_ambiguity():
    db.reset_db()
    first = db.create_commitment({"title": "Math", "tag": "course", "recurrence": "weekly", "days_of_week": [0], "start_time": "09:00", "end_time": "10:00"})
    second = db.create_commitment({"title": "Math Lab", "tag": "course", "recurrence": "weekly", "days_of_week": [0], "start_time": "11:00", "end_time": "12:00"})
    from app.ai.tools import execute_tool
    result = execute_tool("resolve_records", {"entity_type": "commitment", "query": "math", "weekday": 0})
    assert result["success"] is True
    assert result["data"]["ambiguous"] is True
    assert {row["id"] for row in result["data"]["candidates"]} == {first["id"], second["id"]}


def test_change_set_preview_and_apply_updates_commitment_atomically():
    db.reset_db()
    commitment = db.create_commitment({"title": "Agentic AI", "tag": "course", "recurrence": "weekly", "days_of_week": [0], "start_time": "17:00", "end_time": "18:00"})
    # Existing generated future row should be replaced by the updated recurrence.
    db.create_block({"commitment_id": commitment["id"], "title": "Agentic AI", "tag": "course", "start_dt": "2026-11-09T17:00:00", "end_dt": "2026-11-09T18:00:00", "locked": True, "status": "scheduled"})
    proposal = db.create_planning_proposal({
        "request_text": "Rename the Monday course",
        "source": "gemini",
        "structured_plan": {"request_text": "Rename the Monday course", "source": "gemini", "risk_level": "high", "intent": {
            "summary": "Rename Monday course", "projects": [], "tasks": [], "commitments": [], "constraints": {}, "clarifications": [], "assumptions": [],
            "operations": [{"operation": "update", "entity_type": "commitment", "target_id": commitment["id"], "expected_updated_at": commitment["updated_at"], "fields": {"title": "University Agentic AI", "tag": "university"}, "reason": "Monday course match"}],
        }},
    })
    preview = service.preview_proposal(proposal["id"])
    assert preview["preview"]["change_set"]["affected"]["commitment"] == [commitment["id"]]
    assert any(block["title"] == "University Agentic AI" for block in preview["preview"]["blocks"])
    approved = service.approve_proposal(proposal["id"])
    assert approved["status"] == "approved"
    assert db.get_commitment(commitment["id"])["tag"] == "university"
    future = [block for block in db.list_blocks() if block["start_dt"] >= "2026-11-06T00:00:00" and block["status"] == "scheduled"]
    assert future and all(block["title"] == "University Agentic AI" for block in future)


def test_change_set_rejects_stale_target():
    db.reset_db()
    commitment = db.create_commitment({"title": "Original", "tag": "course", "recurrence": "weekly", "days_of_week": [0], "start_time": "17:00", "end_time": "18:00"})
    proposal = db.create_planning_proposal({
        "request_text": "Rename it", "source": "gemini",
        "structured_plan": {"request_text": "Rename it", "source": "gemini", "risk_level": "high", "intent": {
            "summary": "Rename", "projects": [], "tasks": [], "commitments": [], "constraints": {}, "clarifications": [], "assumptions": [],
            "operations": [{"operation": "update", "entity_type": "commitment", "target_id": commitment["id"], "expected_updated_at": commitment["updated_at"], "fields": {"title": "Proposed"}, "reason": "test"}],
        }},
    })
    db.update_commitment(commitment["id"], {"title": "Changed by user"})
    try:
        service.approve_proposal(proposal["id"])
    except ValueError as exc:
        assert "changed" in str(exc)
    else:
        raise AssertionError("stale change set must not apply")
    assert db.get_commitment(commitment["id"])["title"] == "Changed by user"


def test_task_active_until_and_tag_are_persisted_and_scheduler_bound():
    db.reset_db()
    today = date.today().isoformat()
    task = db.create_task({"title": "University routine", "estimated_minutes": 60, "tag": "university", "active_until": today, "preferred_days": [date.today().weekday()], "splittable": False})
    assert task["tag"] == "university"
    assert task["active_until"] == "2026-11-06"
    blocks, unscheduled = schedule([task], [], {**db.get_settings(), "working_days": [date.today().weekday()]}, [], horizon_days=30)
    assert not unscheduled
    assert all(block["start_dt"][:10] <= today for block in blocks if block.get("task_id") == task["id"])


def test_ai_mutation_limit_and_dry_run_are_enforced():
    db.reset_db()
    first = db.create_commitment({"title": "One", "tag": "course", "recurrence": "weekly", "days_of_week": [0], "start_time": "09:00", "end_time": "10:00"})
    second = db.create_commitment({"title": "Two", "tag": "course", "recurrence": "weekly", "days_of_week": [0], "start_time": "11:00", "end_time": "12:00"})
    intent = {"summary": "Bulk rename", "projects": [], "tasks": [], "commitments": [], "constraints": {}, "clarifications": [], "assumptions": [], "operations": [
        {"operation": "update", "entity_type": "commitment", "target_id": first["id"], "expected_updated_at": first["updated_at"], "fields": {"tag": "university"}},
        {"operation": "update", "entity_type": "commitment", "target_id": second["id"], "expected_updated_at": second["updated_at"], "fields": {"tag": "university"}},
    ]}
    proposal = db.create_planning_proposal({"request_text": "bulk", "source": "gemini", "structured_plan": {"request_text": "bulk", "source": "gemini", "risk_level": "high", "intent": intent}})
    db.save_settings({**db.get_settings(), "ai_max_mutations": 1})
    try:
        service.preview_proposal(proposal["id"])
    except ValueError as exc:
        assert "limit" in str(exc)
    else:
        raise AssertionError("mutation limit must be enforced")

    db.save_settings({**db.get_settings(), "ai_max_mutations": 25, "ai_dry_run": True})
    proposal2 = db.create_planning_proposal({"request_text": "rename", "source": "gemini", "structured_plan": {"request_text": "rename", "source": "gemini", "risk_level": "high", "intent": {**intent, "operations": [intent["operations"][0]]}}})
    result = service.approve_proposal(proposal2["id"])
    assert result["status"] == "dry_run"
    assert db.get_commitment(first["id"])["tag"] == "course"


def test_approved_change_set_can_be_reverted():
    db.reset_db()
    commitment = db.create_commitment({"title": "Original", "tag": "course", "recurrence": "weekly", "days_of_week": [0], "start_time": "09:00", "end_time": "10:00"})
    proposal = db.create_planning_proposal({"request_text": "rename", "source": "gemini", "structured_plan": {"request_text": "rename", "source": "gemini", "risk_level": "high", "intent": {"summary": "rename", "projects": [], "tasks": [], "commitments": [], "constraints": {}, "clarifications": [], "assumptions": [], "operations": [{"operation": "update", "entity_type": "commitment", "target_id": commitment["id"], "expected_updated_at": commitment["updated_at"], "fields": {"title": "Updated"}}]}}})
    service.preview_proposal(proposal["id"])
    service.approve_proposal(proposal["id"])
    assert db.get_commitment(commitment["id"])["title"] == "Updated"
    reverted = db.revert_planning_proposal(proposal["id"])
    assert reverted
    assert db.get_commitment(commitment["id"])["title"] == "Original"
