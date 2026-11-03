import json
from typing import Optional

class ProviderError(RuntimeError):
    def __init__(self, message, *, kind="provider_error", retryable=False):
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable

EXTRACTION_PROMPT = """You are a planning assistant. Extract structured planning information from the user's natural language request.
Return ONLY valid JSON with this shape:
{
  "summary": "short summary",
  "tasks": [
    {"title": "...", "description": "...", "estimated_minutes": 60, "deadline": "YYYY-MM-DD or null", "priority": 3, "preferred_days": [0-6], "preferred_start": "HH:MM or null", "preferred_end": "HH:MM or null", "min_session_minutes": 25, "max_session_minutes": 90, "splittable": true, "flexible": true, "dependencies": []}
  ],
  "commitments": [
    {"title": "...", "tag": "university|personal|course|project", "recurrence": "weekly|once", "days_of_week": [0-6], "start_time": "HH:MM", "end_time": "HH:MM", "one_time_date": "YYYY-MM-DD or null", "start_date": null, "end_date": null}
  ],
  "projects": [
    {"name": "...", "description": "...", "kind": "project|course", "total_sessions": 0, "session_minutes": 60, "target_deadline": "YYYY-MM-DD or null"}
  ],
  "clarifications": ["questions if ambiguous"]
}
Days: 0=Monday. If the user mentions "half a session" etc, convert to minutes. Keep tasks concrete.
User request: 
"""

class AIProvider:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
    def is_configured(self):
        return bool(self.api_key)
    def capabilities(self):
        return {"structured_output": False, "tool_calling": False, "streaming": False}
    def extract(self, text: str) -> dict:
        raise NotImplementedError
    def chat(self, text: str) -> str:
        raise NotImplementedError
