"""Phase 1 tests — AI planning end-to-end, provider configuration, tool calling.

Refine.txt §2 (§2 fix AI planning end-to-end), §3 (§3 AI provider configuration),
§5 (§5 verify tool calling).

Uses the temp-DB fixture (conftest.py) — never mutates backend/data/monolith.db.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest  # noqa: E402
import httpx  # noqa: E402

from app import db  # noqa: E402
from app.ai import service  # noqa: E402
from app.ai.base import ProviderError  # noqa: E402
from app.ai.gemini import GeminiProvider  # noqa: E402
from app.ai.tools import execute_tool  # noqa: E402


# ---------------------------------------------------------------------------
# T1.1 — Provider configuration is actually used (provider + model)
# ---------------------------------------------------------------------------

def _gemini_settings():
    return {**db.get_settings(), "ai_provider": "gemini",
            "ai_api_key": "sk-test-key-12345", "ai_model": "gemini-2.0-flash"}


def test_gemini_provider_used_with_selected_model(monkeypatch):
    """Selected provider and model are actually used in the provider call."""
    db.reset_db()
    db.save_settings(_gemini_settings())

    captured = {}

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "candidates": [{
                    "content": {
                        "parts": [{"text": json.dumps({
                            "summary": "Test plan",
                            "tasks": [{"title": "Write report",
                                       "estimated_minutes": 60, "deadline": None,
                                       "priority": 3, "preferred_days": [],
                                       "preferred_start": None, "preferred_end": None,
                                       "min_session_minutes": 25, "max_session_minutes": 90,
                                       "splittable": True, "flexible": True,
                                       "dependencies": []}],
                            "commitments": [], "projects": [], "clarifications": []
                        })}]}
                }]
            }

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResp()

    monkeypatch.setattr("httpx.post", fake_post)

    result = service.plan_request("I have a project due Friday")

    assert result["source"] == "gemini", result
    assert "gemini-2.0-flash" in captured["url"], captured["url"]
    # The model/api key from settings were actually sent to the provider.
    assert "sk-test-key-12345" in captured["url"]
    assert result["proposal"]["intent"]["tasks"][0]["title"] == "Write report"


# ---------------------------------------------------------------------------
# T1.2 — Provider API errors are surfaced clearly (no silent offline fallback)
# ---------------------------------------------------------------------------

def _raise_extract(self, text):
    raise ProviderError("invalid API key", kind="authentication", retryable=False)


def test_plan_request_surfaces_provider_error(monkeypatch):
    """Configured provider failure → ai_error present, offline fallback flagged."""
    db.reset_db()
    db.save_settings(_gemini_settings())
    monkeypatch.setattr(GeminiProvider, "extract", _raise_extract)

    result = service.plan_request("I have a project due Friday")

    # App stays usable via offline fallback.
    assert result["source"] == "offline"
    assert result["configured"] is False
    # But the failure is clearly reported, not silently hidden.
    assert "ai_error" in result, result
    assert result["ai_error"]["kind"] == "authentication"
    assert "invalid API key" in result["ai_error"]["message"]
    assert "unavailable" in result["message"]
    # Offline proposal is still returned so the user is not blocked.
    assert "proposal" in result


def test_extract_and_preview_surfaces_provider_error(monkeypatch):
    """extract_and_preview also reports ai_error instead of swallowing."""
    db.reset_db()
    db.save_settings(_gemini_settings())
    monkeypatch.setattr(GeminiProvider, "extract", _raise_extract)

    result = service.extract_and_preview("do something")

    assert result["source"] == "offline"
    assert "ai_error" in result
    assert result["ai_error"]["kind"] == "authentication"
    assert "proposal" in result


# ---------------------------------------------------------------------------
# T1.6 — App remains usable without AI (offline plan → preview → approve → persist)
# ---------------------------------------------------------------------------

def test_usable_without_ai_offline_flow_persists():
    """No AI provider → offline planner, full preview/approve flow persists to SQLite."""
    db.reset_db()
    # ai_provider defaults to "none" after reset_db; no env key set either.
    settings = db.get_settings()
    assert settings["ai_provider"] == "none"

    result = service.plan_request("Add task Review notes for 30 minutes")
    assert result["source"] == "offline"
    assert "ai_error" not in result
    task_intent = result["proposal"]["intent"]["tasks"][0]
    assert task_intent["estimated_minutes"] == 30

    pid = result["proposal_id"]
    preview = service.preview_proposal(pid)
    assert preview["status"] == "previewed"

    approved = service.approve_proposal(pid)
    assert approved["status"] == "approved"

    # Everything persisted in SQLite.
    tasks = db.list_tasks()
    assert len(tasks) == 1
    assert tasks[0]["estimated_minutes"] == 30
    blocks = db.list_blocks()
    assert len(blocks) == 1


# ---------------------------------------------------------------------------
# T1.5 — Tool calling: read operations
# ---------------------------------------------------------------------------

def test_tool_read_operations():
    db.reset_db()
    proj = db.create_project({"name": "Alpha", "kind": "project"})
    db.create_task({"title": "Task A", "estimated_minutes": 60, "remaining_minutes": 60})
    db.create_commitment({
        "title": "Weekly Class", "kind": "fixed", "tag": "university",
        "recurrence": "weekly", "days_of_week": [2],
        "start_time": "10:00", "end_time": "12:00",
    })

    assert execute_tool("get_calendar_events")["success"] is True
    assert len(execute_tool("get_calendar_events")["data"]) == 0
    assert len(execute_tool("get_projects")["data"]) == 1
    assert len(execute_tool("get_tasks")["data"]) == 1
    assert len(execute_tool("get_commitments")["data"]) == 1
    assert execute_tool("get_project_progress", {"project_id": proj["id"]})["success"] is True


# ---------------------------------------------------------------------------
# T1.5 — Tool calling: create / write operations (confirmation enforced)
# ---------------------------------------------------------------------------

def test_tool_create_requires_confirmation_then_executes():
    db.reset_db()
    # Without confirmation, consequential writes are rejected.
    res = execute_tool("create_task", {"title": "Unconfirmed", "estimated_minutes": 30})
    assert res["confirmation_required"] is True
    assert res["success"] is False
    assert db.list_tasks() == []

    # With confirmation, it executes.
    res = execute_tool("create_task", {"title": "Confirmed", "estimated_minutes": 30},
                       confirmed=True, conversation_id="c")
    assert res["success"] is True
    assert len(db.list_tasks()) == 1
    assert db.list_tasks()[0]["title"] == "Confirmed"


def test_tool_create_project_and_commitment():
    db.reset_db()
    res = execute_tool("create_project", {"name": "Course X", "kind": "course",
                                          "total_sessions": 5}, confirmed=True)
    assert res["success"] is True
    assert db.list_projects()[0]["name"] == "Course X"

    res = execute_tool("create_commitment", {
        "title": "CS101", "kind": "fixed", "tag": "university",
        "recurrence": "weekly", "days_of_week": [2],
        "start_time": "10:00", "end_time": "12:00",
    }, confirmed=True)
    assert res["success"] is True
    assert len(db.list_commitments()) == 1


def test_tool_complete_and_update_task():
    db.reset_db()
    t = db.create_task({"title": "To complete", "estimated_minutes": 60, "remaining_minutes": 60})
    res = execute_tool("complete_task", {"task_id": t["id"]}, conversation_id="c")
    assert res["success"] is True
    assert db.get_task(t["id"])["status"] == "done"

    res = execute_tool("update_task", {"task_id": t["id"], "title": "Renamed",
                                       "estimated_minutes": 90}, confirmed=True)
    assert res["success"] is True
    assert db.get_task(t["id"])["title"] == "Renamed"


# ---------------------------------------------------------------------------
# T1.5 / G4 — Skip tool refunds scheduled minutes back to the task
# ---------------------------------------------------------------------------

def test_skip_tool_refunds_minutes():
    db.reset_db()
    proj = db.create_project({"name": "P", "kind": "project"})
    t = db.create_task({"project_id": proj["id"], "title": "Session", "estimated_minutes": 60,
                        "remaining_minutes": 60, "status": "todo"})
    db.create_block({
        "task_id": t["id"], "title": "Session",
        "start_dt": "2026-11-09T09:00:00", "end_dt": "2026-11-09T10:00:00",
        "status": "scheduled", "locked": 0,
    })

    res = execute_tool("skip_task", {"task_id": t["id"]}, confirmed=True, conversation_id="c")
    assert res["success"] is True
    task = db.get_task(t["id"])
    assert task["remaining_minutes"] == 120, f"Expected refund to 120, got {task['remaining_minutes']}"
    assert db.list_blocks()[0]["status"] == "skipped"
