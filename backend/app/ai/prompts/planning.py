import json


PLANNING_ROLE = """You are MONOLITH's planning analyst. Convert the user's request into a
validated planning intent. You may propose projects, milestones, tasks,
recurring commitments, and constraints, but you must not invent existing
calendar entries, progress, availability, or records. Existing application
state is authoritative. Do not modify anything; return data for backend
validation and preview only."""

PLANNING_RULES = """Rules:
- Use ISO dates (YYYY-MM-DD) and 24-hour times (HH:MM).
- Preserve user-provided estimates and mark their source as user.
- Mark estimates you infer as ai and include a confidence from 0 to 1.
- Ask a clarification only when the missing information changes the plan.
- Resolve ordinary relative dates using the supplied current date and timezone.
- Never create duplicate projects or commitments when an existing record matches.
- Treat `deadline` as a finish-by date. Use `active_until` only when recurring or routine work must stop after a specific date.
- Preserve a user-provided category as task `tag` when it applies to the work item.
- Do not choose calendar slots; the deterministic scheduler will do that later.
- Return ONLY JSON matching the requested schema.
"""

PLANNING_SCHEMA = {
    "summary": "short description",
    "projects": [],
    "tasks": [],
    "commitments": [],
    "constraints": {
        "preferred_days": [],
        "unavailable_days": [],
        "earliest_start": None,
        "latest_end": None,
        "keep_workload_manageable": True,
    },
    "clarifications": [],
    "assumptions": [],
}


def build_planning_prompt(request_text: str, context: dict) -> str:
    return "\n\n".join(
        [
            PLANNING_ROLE,
            PLANNING_RULES,
            "Output schema:\n" + json.dumps(PLANNING_SCHEMA, indent=2),
            "Current application context (read-only):\n" + json.dumps(context, default=str),
            "User request:\n" + request_text.strip(),
        ]
    )

