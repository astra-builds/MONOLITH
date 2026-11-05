"""Phase 2 — Autonomous planning tests (Refine.txt §6).

Covers the scenarios NOT yet exercised by the existing suite:
  F. Follow-up request modifying an existing plan.
  I. Invalid AI structured output.
  J. Duplicate planning request.

Plus a regression assertion that previously covered scenarios still hold.
Uses the temp-DB fixture (conftest.py) — never mutates backend/data/monolith.db.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest  # noqa: E402

from app import db  # noqa: E402
from app.ai import service  # noqa: E402
from app.ai.gemini import GeminiProvider  # noqa: E402
from app.ai.base import ProviderError  # noqa: E402
from app.ai.tools import execute_tool  # noqa: E402


# ---------------------------------------------------------------------------
# F. Follow-up request modifying an existing plan
# ---------------------------------------------------------------------------

def test_follow_up_completion_modifies_existing_plan_no_duplicates():
    """F: A follow-up ("I completed X") modifies the existing plan state —
    marking the task done and its scheduled blocks completed — without
    creating duplicate tasks or blocks.
    """
    db.reset_db()
    proj = db.create_project({"name": "Course", "kind": "course"})
    t = db.create_task({
        "project_id": proj["id"],
        "title": "Agentic AI - Session 01.1",
        "estimated_minutes": 60,
        "remaining_minutes": 60,
        "status": "todo",
        "splittable": False,
    })
    # Schedule a block for it.
    db.create_block({
        "task_id": t["id"], "title": t["title"],
        "start_dt": "2026-11-07T09:00:00", "end_dt": "2026-11-07T10:00:00",
        "status": "scheduled", "locked": 0,
    })
    before_blocks = len(db.list_blocks())
    before_tasks = len(db.list_tasks())

    # Follow-up message modifying the existing plan.
    resp = service.handle_conversation_message(
        "conv-f", f"I completed {t['title']}", confirm=True,
    )

    assert resp["type"] == "tool_result"
    assert resp["tool"]["success"] is True
    # Existing plan modified: task done.
    assert db.get_task(t["id"])["status"] == "done"
    # Existing plan modified: its scheduled block marked completed.
    blocks = db.list_blocks()
    assert any(b["task_id"] == t["id"] and b["status"] == "completed"
               for b in blocks)
    # No duplicates created by the follow-up.
    assert len(db.list_tasks()) == before_tasks
    assert len(db.list_blocks()) == before_blocks


# ---------------------------------------------------------------------------
# I. Invalid AI structured output
# ---------------------------------------------------------------------------

def _bad_extract(self, text):
    """Return out-of-schema structured output (invalid weekday 7)."""
    return {
        "summary": "Bad plan",
        "tasks": [{
            "title": "Bad Task",
            "estimated_minutes": 60,
            "preferred_days": [7],  # invalid: must be 0-6
            "splittable": True,
            "flexible": True,
        }],
        "commitments": [], "projects": [], "clarifications": [],
    }


def test_invalid_ai_structured_output_raises_clear_error_and_persists_nothing():
    """I: Provider returns invalid structured output → clear ValueError,
    no proposal persisted, workspace untouched.
    """
    db.reset_db()
    db.save_settings({**db.get_settings(), "ai_provider": "gemini",
                      "ai_api_key": "sk-test-key", "ai_model": "gemini-2.0-flash"})
    # Monkeypatch the provider to emit invalid output.
    orig = GeminiProvider.extract
    GeminiProvider.extract = _bad_extract
    try:
        with pytest.raises(ValueError) as exc:
            service.plan_request("Add a bad task")
        assert "validation" in str(exc.value).lower() or "preferred_days" in str(exc.value)
    finally:
        GeminiProvider.extract = orig

    # Nothing persisted — proposal not saved as valid, workspace untouched.
    assert db.list_projects() == []
    assert db.list_tasks() == []
    assert db.list_commitments() == []
    assert db.list_blocks() == []
    # No planning proposal survived a failed validation (plan_request raises
    # before create_planning_proposal, so the proposals table is unchanged).
    with db.connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM planning_proposals").fetchone()[0]
    assert count == 0


# ---------------------------------------------------------------------------
# J. Duplicate planning request
# ---------------------------------------------------------------------------

def test_duplicate_planning_request_idempotent_at_proposal_level():
    """J: The same planning request can be issued twice (two proposals),
    and re-approving an already-approved proposal is blocked (idempotent),
    so it never re-applies or duplicates work.
    """
    db.reset_db()
    result1 = service.plan_request("Add task Review notes for 30 minutes")
    result2 = service.plan_request("Add task Review notes for 30 minutes")

    # Two distinct proposals created (safe to re-plan).
    assert result1["proposal_id"] != result2["proposal_id"]
    assert result1["source"] == "offline"
    assert result2["source"] == "offline"

    # Approve the first → applies and persists.
    approved1 = service.approve_proposal(result1["proposal_id"])
    assert approved1["status"] == "approved"
    assert len(db.list_tasks()) == 1

    # Re-approving the SAME proposal is blocked (idempotent — no re-apply).
    with pytest.raises(ValueError) as exc:
        service.approve_proposal(result1["proposal_id"])
    assert "already approved" in str(exc.value).lower() or "already" in str(exc.value).lower()

    # Still exactly one task — no duplicate from the blocked re-approve.
    assert len(db.list_tasks()) == 1

    # The second (separate) proposal can still be approved on its own merit;
    # it creates its own records (a distinct request, not a re-apply).
    approved2 = service.approve_proposal(result2["proposal_id"])
    assert approved2["status"] == "approved"
