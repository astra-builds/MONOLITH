"""Deterministic offline natural-language planning parser for MONOLITH.

Allows MONOLITH to operate 100% locally without requiring external API keys
or cloud services. Extracts projects, courses, tasks, and fixed commitments
using pattern recognition, regex heuristics, and structured rules.
"""

import re
from datetime import date, datetime, timedelta

DAY_NAMES_MAP = {
    "mon": 0, "monday": 0,
    "tue": 1, "tues": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}

def parse_offline(text: str) -> dict:
    """Parse natural language into a structured proposal dict.

    Returns dict with keys:
        summary: str
        projects: list[dict]
        tasks: list[dict]
        commitments: list[dict]
        clarifications: list[str]
    """
    raw = text.strip()
    lower = raw.lower()

    projects = []
    tasks = []
    commitments = []
    clarifications = []
    summary_parts = []

    # ------------------------------------------------------------------
    # 1. Course / Project pattern
    # E.g. "I have an Agentic AI course with 10 sessions. I want to complete
    # half a session every Saturday."
    # ------------------------------------------------------------------
    is_course = "course" in lower or "class sessions" in lower or "lessons" in lower
    is_project = "project" in lower and not is_course

    if is_course:
        # Extract title
        title_match = re.search(r'(?:an?|add)\s+([a-zA-Z0-9_\-\s]+?)\s+course', raw, re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'course\s+(?:on|for|named)?\s*([a-zA-Z0-9_\-\s]+?)(?:with|\.|,|\b\d+\b)', raw, re.IGNORECASE)
        course_name = title_match.group(1).strip() if title_match else "Course Study"
        course_name = re.sub(r'^(?:have\s+an?|add|create)\s+', '', course_name, flags=re.IGNORECASE).strip()

        # Extract session count
        sess_match = re.search(r'(\d+)\s*(?:sessions?|lessons?|modules?|lectures?|classes?)', lower)
        total_sessions = int(sess_match.group(1)) if sess_match else 0

        # Extract duration
        hours_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b', lower)
        mins_match = re.search(r'(\d+)\s*(?:minutes?|mins?|m)\b', lower)
        session_mins = 120
        if hours_match:
            session_mins = int(float(hours_match.group(1)) * 60)
        elif mins_match:
            session_mins = int(mins_match.group(1))

        # Check for half session
        is_half = "half a session" in lower or "half session" in lower or "half-session" in lower or "split" in lower

        # Extract preferred day
        preferred_days = []
        for word, d_idx in DAY_NAMES_MAP.items():
            if re.search(rf'\b(?:every|on)?\s*{word}\b', lower):
                if d_idx not in preferred_days:
                    preferred_days.append(d_idx)

        if not preferred_days:
            preferred_days = [5]  # default Saturday

        # Check for missing info -> add clarifications
        if total_sessions == 0:
            total_sessions = 10
            clarifications.append("Course session count not specified; defaulted to 10 sessions.")

        block_count = total_sessions * 2 if is_half else total_sessions
        block_dur = session_mins // 2 if is_half else session_mins

        projects.append({
            "name": course_name,
            "description": f"{course_name} ({total_sessions} sessions)",
            "kind": "course",
            "total_sessions": total_sessions,
            "session_minutes": session_mins,
            "target_deadline": None,
        })

        # Generate tasks linked with sequential dependency
        for i in range(block_count):
            if is_half:
                s_num = i // 2 + 1
                sub = i % 2 + 1
                t_title = f"{course_name} - Session {s_num:02d}.{sub}"
            else:
                t_title = f"{course_name} - Session {i + 1:02d}"

            # Dependency token for sequential chaining
            dep_ref = ["__PREV__"] if i > 0 else []

            tasks.append({
                "title": t_title,
                "project_name": course_name,
                "estimated_minutes": block_dur,
                "remaining_minutes": block_dur,
                "preferred_days": preferred_days,
                "splittable": False,
                "flexible": True,
                "priority": 3,
                "dependencies": dep_ref,
            })

        summary_parts.append(f"Course '{course_name}' ({block_count} study blocks of {block_dur}m)")

    # ------------------------------------------------------------------
    # 2. Fixed Commitments (University classes, recurring routines)
    # E.g. "University classes during the week", "CS101 on Wednesday 10:00 to 12:00"
    # ------------------------------------------------------------------
    class_matches = re.finditer(
        r'(?:class|lecture|lab|seminar|meeting|sync|routine)\s*:?\s*([a-zA-Z0-9_\-\s]+?)\s+(?:on|every)?\s*([a-zA-Z]+)\s+(?:at\s+)?(\d{1,2}(?::\d{2})?)\s*(?:-|to)\s*(\d{1,2}(?::\d{2})?)',
        raw,
        re.IGNORECASE
    )
    found_any_class = False
    for m in class_matches:
        found_any_class = True
        c_title = m.group(1).strip()
        day_str = m.group(2).strip().lower()
        st_raw = m.group(3).strip()
        et_raw = m.group(4).strip()

        day_idx = DAY_NAMES_MAP.get(day_str, 2)
        st = st_raw if ":" in st_raw else f"{int(st_raw):02d}:00"
        et = et_raw if ":" in et_raw else f"{int(et_raw):02d}:00"

        tag = "university" if ("uni" in lower or "cs" in c_title.lower() or "math" in c_title.lower()) else "personal"

        commitments.append({
            "title": c_title,
            "kind": "fixed",
            "tag": tag,
            "recurrence": "weekly",
            "days_of_week": [day_idx],
            "start_time": st,
            "end_time": et,
        })
        summary_parts.append(f"Fixed commitment '{c_title}' ({day_str.capitalize()} {st}–{et})")

    # Recurring routines: e.g. "Mondays are for my personal project, and Tuesdays are for university work"
    if "monday" in lower and ("personal project" in lower or "project" in lower) and not found_any_class:
        commitments.append({
            "title": "Personal Project Focus",
            "kind": "fixed",
            "tag": "personal",
            "recurrence": "weekly",
            "days_of_week": [0],  # Monday
            "start_time": "09:00",
            "end_time": "13:00",
        })
        summary_parts.append("Routine: Personal Project (Mon 09:00–13:00)")

    if "tuesday" in lower and ("university" in lower or "academic" in lower) and not found_any_class:
        commitments.append({
            "title": "University Academic Study",
            "kind": "fixed",
            "tag": "university",
            "recurrence": "weekly",
            "days_of_week": [1],  # Tuesday
            "start_time": "09:00",
            "end_time": "13:00",
        })
        summary_parts.append("Routine: University Study (Tue 09:00–13:00)")

    # ------------------------------------------------------------------
    # 3. Individual Task Pattern
    # E.g. "Add task Study Paxos due 2026-11-15 duration 90m"
    # ------------------------------------------------------------------
    if not is_course and ("task" in lower or "todo" in lower or "assignment" in lower):
        task_name_match = re.search(r'(?:add\s+)?(?:task|todo|assignment)\s*:?\s*([a-zA-Z0-9_\-\s]+?)(?:due|in|\d+h|\d+m|$)', raw, re.IGNORECASE)
        t_name = task_name_match.group(1).strip() if task_name_match else "New Task"

        dur_h = re.search(r'(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b', lower)
        dur_m = re.search(r'(\d+)\s*(?:minutes?|mins?|m)\b', lower)
        mins = 60
        if dur_h:
            mins = int(float(dur_h.group(1)) * 60)
        elif dur_m:
            mins = int(dur_m.group(1))

        deadline_match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', raw)
        dl = deadline_match.group(1) if deadline_match else None

        tasks.append({
            "title": t_name,
            "estimated_minutes": mins,
            "remaining_minutes": mins,
            "deadline": dl,
            "priority": 3,
            "splittable": True,
            "flexible": True,
        })
        summary_parts.append(f"Task '{t_name}' ({mins}m)")

    summary = "; ".join(summary_parts) if summary_parts else f"Plan for: {raw[:50]}"

    return {
        "summary": summary,
        "projects": projects,
        "tasks": tasks,
        "commitments": commitments,
        "clarifications": clarifications,
    }
