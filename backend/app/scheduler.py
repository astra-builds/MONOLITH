"""
MONOLITH Scheduling Engine
===========================
Pure-function scheduler: receives all data as arguments, never touches the DB.

Implements 13 scheduling rules:
 1. Respect fixed commitments / unavailable time
 2. Respect weekly availability (working_days) and working hours
 3. Schedule tasks before their deadlines whenever possible
 4. Prioritise urgent/important tasks (lower priority = higher importance)
 5. Respect dependencies — use full datetime, not just date
 6. Respect preferred days and recurring routines
 7. Split large tasks ONLY when splittable is True
 8. Respect min/max session durations
 9. Include min_break_minutes gap between consecutive sessions on a day
10. daily_used includes BOTH commitment and task minutes, capped at max_daily_minutes
11. Leave reasonable free time (max_daily_minutes cap)
12. Spread long-term work across available days
13. Never silently discard a task — always report detailed reason

Dates: ISO format strings (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
Weekdays: 0=Monday … 6=Sunday (Python convention)
"""

from datetime import datetime, timedelta, date, time, timezone
from collections import defaultdict

# ---------------------------------------------------------------------------
# Parsing / formatting helpers
# ---------------------------------------------------------------------------

def parse_date(s):
    """Parse an ISO date string to a ``date`` object.
    Handles both 'YYYY-MM-DD' and 'YYYY-MM-DDTHH:MM:SS' forms.
    """
    if s is None:
        return None
    if isinstance(s, date) and not isinstance(s, datetime):
        return s
    if isinstance(s, datetime):
        return s.date()
    dt = parse_dt(s)
    return dt.date() if dt else None


def parse_dt(s):
    """Parse an ISO datetime string to a naive ``datetime`` object."""
    if s is None:
        return None
    if isinstance(s, datetime):
        d = s
    else:
        d = datetime.fromisoformat(s)
    if d.tzinfo is not None:
        d = d.astimezone(timezone.utc).replace(tzinfo=None)
    return d


def fmt_dt(d):
    """Format a ``datetime`` to an ISO string without microseconds."""
    return d.replace(microsecond=0).isoformat()


def parse_time(s):
    """Parse 'HH:MM' or 'HH:MM:SS' into ``(hour, minute)`` ints."""
    parts = s.split(":")
    return int(parts[0]), int(parts[1])


# ---------------------------------------------------------------------------
# Commitment block generation
# ---------------------------------------------------------------------------

def generate_commitment_blocks(commitments, start_date, end_date):
    """Expand recurring / one-time commitments into concrete interval dicts
    covering ``[start_date, end_date]``.

    Each returned dict has keys:
        start, end        – datetime objects
        locked            – True
        title, tag        – copied from the commitment
        commitment_id     – id of the source commitment
    """
    blocks = []
    cur = start_date
    while cur <= end_date:
        for c in commitments:
            recurrence = c.get("recurrence", "once")
            if recurrence == "weekly":
                if cur.weekday() not in (c.get("days_of_week") or []):
                    continue
                if c.get("start_date") and cur < parse_date(c["start_date"]):
                    continue
                if c.get("end_date") and cur > parse_date(c["end_date"]):
                    continue
            elif recurrence == "daily":
                if c.get("start_date") and cur < parse_date(c["start_date"]):
                    continue
                if c.get("end_date") and cur > parse_date(c["end_date"]):
                    continue
            elif recurrence == "once":
                if not c.get("one_time_date") or parse_date(c["one_time_date"]) != cur:
                    continue
            else:
                continue

            sh, sm = parse_time(c["start_time"])
            eh, em = parse_time(c["end_time"])
            s = datetime(cur.year, cur.month, cur.day, sh, sm)
            e = datetime(cur.year, cur.month, cur.day, eh, em)
            if e <= s:
                # If end ≤ start treat as 30-min block (defensive)
                e = s + timedelta(minutes=30)
            blocks.append({
                "start": s,
                "end": e,
                "locked": True,
                "title": c["title"],
                "tag": c.get("tag", "commitment"),
                "commitment_id": c["id"],
            })
        cur += timedelta(days=1)
    return blocks


# ---------------------------------------------------------------------------
# Topological + priority sort
# ---------------------------------------------------------------------------

def topo_sort(tasks):
    """Return *tasks* in dependency-safe order.

    Within each topological level tasks are further sorted by:
      1. deadline (earliest first, tasks without deadline last)
      2. priority (lower number = more important = first)
      3. remaining_minutes descending (spread bigger tasks earlier)
    """
    by_id = {t["id"]: t for t in tasks}
    # Build adjacency / in-degree for Kahn's algorithm
    in_degree = {t["id"]: 0 for t in tasks}
    dependents = defaultdict(list)  # prerequisite -> list of dependents

    for t in tasks:
        for dep in (t.get("dependencies") or []):
            if dep in by_id:
                in_degree[t["id"]] += 1
                dependents[dep].append(t["id"])

    far_future = date(9999, 12, 31)

    def _sort_key(tid):
        t = by_id[tid]
        dl = parse_date(t["deadline"]) if t.get("deadline") else far_future
        prio = t.get("priority", 5)
        remaining = -(t.get("remaining_minutes", 0) or 0)  # negative = bigger first
        return (dl, prio, remaining)

    queue = sorted(
        [tid for tid, deg in in_degree.items() if deg == 0],
        key=_sort_key,
    )
    result = []
    while queue:
        # Process current level (all items at this frontier) sorted
        next_queue_ids = []
        for tid in queue:
            result.append(by_id[tid])
            for dep_tid in dependents[tid]:
                in_degree[dep_tid] -= 1
                if in_degree[dep_tid] == 0:
                    next_queue_ids.append(dep_tid)
        queue = sorted(next_queue_ids, key=_sort_key)

    # Any remaining tasks with non-zero in_degree have cyclic deps — append
    # them anyway so they end up in the unscheduled list with a reason.
    for t in tasks:
        if t["id"] not in {r["id"] for r in result}:
            result.append(t)
    return result


# ---------------------------------------------------------------------------
# Session splitting
# ---------------------------------------------------------------------------

def split_sessions(task):
    """Break a task's ``remaining_minutes`` into session durations.

    Rule 7: Only split when ``task['splittable']`` is ``True``.
    Rule 8: Respect min/max session durations.

    Returns a list of ints (minutes per session).  Empty if nothing to schedule.
    """
    remaining = task.get("remaining_minutes", 0) or 0
    if remaining <= 0:
        return []

    max_sess = task.get("max_session_minutes") or 90
    min_sess = task.get("min_session_minutes") or 25

    # --- NOT splittable → single block ---
    if not task.get("splittable", True):
        return [remaining]

    # --- Splittable ---
    sessions = []
    r = remaining
    while r > 0:
        dur = min(max_sess, r)
        r -= dur
        # If the leftover would be smaller than min_session, merge it back
        if 0 < r < min_sess:
            dur += r
            r = 0
        sessions.append(dur)
    return sessions


# ---------------------------------------------------------------------------
# Tag / reason helpers
# ---------------------------------------------------------------------------

def tag_for_task(t, project_map=None):
    """Derive a tag string for the task from its project (if any)."""
    if project_map and t.get("project_id") in (project_map or {}):
        kind = project_map[t["project_id"]].get("kind")
        if kind:
            return kind
    return t.get("tag", "task")


def _day_label(d):
    """Human-friendly day label like 'Saturday 10:00'."""
    return d.strftime("%A %H:%M")


def _build_placement_reason(task, slot_start, slot_end, preferred_days,
                            commitment_conflicts=None):
    """Return a descriptive reason string for WHY a session was placed here."""
    parts = [f"Scheduled {_day_label(slot_start)}–{slot_end.strftime('%H:%M')}"]
    if preferred_days and slot_start.weekday() in preferred_days:
        parts.append("matches preferred day")
    parts.append("has available capacity")
    if commitment_conflicts:
        parts.append(f"avoids commitments: {', '.join(commitment_conflicts)}")
    else:
        parts.append("does not conflict with commitments")
    return ": " .join([parts[0], ", ".join(parts[1:])]) + "."


def _build_unscheduled_reason(task, detail, blocking_commitments=None,
                              available_minutes=None):
    """Return a descriptive reason string for WHY a task could NOT be placed."""
    remaining = task.get("remaining_minutes", 0) or 0
    deadline_str = task.get("deadline", "none")
    lines = [detail]
    if task.get("deadline"):
        lines.append(f"Deadline {deadline_str}.")
    lines.append(f"Required: {_fmt_hours(remaining)}.")
    if available_minutes is not None:
        lines.append(f"Available before deadline: {_fmt_hours(available_minutes)}.")
    if blocking_commitments:
        lines.append(f"Blocked by: {', '.join(blocking_commitments)}.")
    return " ".join(lines)


def _fmt_hours(minutes):
    """Format minutes as '1h 30min' or '45min'."""
    h, m = divmod(int(minutes), 60)
    if h and m:
        return f"{h}h {m}min"
    if h:
        return f"{h}h"
    return f"{m}min"


# ---------------------------------------------------------------------------
# Completion estimate
# ---------------------------------------------------------------------------

def estimate_completion(task, blocks):
    """Return the latest ``end_dt`` among scheduled blocks for *task*,
    or ``None`` if nothing is scheduled."""
    ts = [b for b in blocks if b.get("task_id") == task["id"]]
    if not ts:
        return None
    return max(b["end_dt"] for b in ts)


# ---------------------------------------------------------------------------
# Schedule diff
# ---------------------------------------------------------------------------

def schedule_diff(old_blocks, new_blocks):
    """Compare two sets of schedule blocks and return a structured diff.

    Returns a dict with keys ``created``, ``moved``, ``removed``, ``unchanged``.
    Blocks are matched on ``(task_id, commitment_id, title)``.
    A block is considered *moved* if the matched block has different start/end.
    """
    def _key(b):
        return (b.get("task_id"), b.get("commitment_id"), b.get("title"))

    old_by_key = {}
    for b in old_blocks:
        old_by_key.setdefault(_key(b), []).append(b)

    new_by_key = {}
    for b in new_blocks:
        new_by_key.setdefault(_key(b), []).append(b)

    created = []
    moved = []
    unchanged = []
    removed = []

    all_keys = set(list(old_by_key.keys()) + list(new_by_key.keys()))
    for key in all_keys:
        old_list = old_by_key.get(key, [])
        new_list = new_by_key.get(key, [])

        # Match by position within key group
        for i, nb in enumerate(new_list):
            if i < len(old_list):
                ob = old_list[i]
                if ob.get("start_dt") == nb.get("start_dt") and ob.get("end_dt") == nb.get("end_dt"):
                    unchanged.append(nb)
                else:
                    moved.append({"old": ob, "new": nb})
            else:
                created.append(nb)

        # Old blocks not matched → removed
        if len(old_list) > len(new_list):
            for ob in old_list[len(new_list):]:
                removed.append(ob)

    return {
        "created": created,
        "moved": moved,
        "removed": removed,
        "unchanged": unchanged,
    }


# ---------------------------------------------------------------------------
# Main scheduling engine
# ---------------------------------------------------------------------------

def schedule(tasks, commitments, settings, existing_blocks, projects=None,
             horizon_days=180):
    """Build a full schedule for all *tasks* respecting *commitments*, user
    *settings*, and already-locked *existing_blocks*.

    Parameters
    ----------
    tasks : list[dict]
        Task dicts with keys like id, title, remaining_minutes, deadline,
        priority, dependencies, splittable, preferred_days, min_session_minutes,
        max_session_minutes, preferred_start, preferred_end, status, project_id.
    commitments : list[dict]
        Fixed commitments (weekly / once / daily).
    settings : dict
        working_days, working_start, working_end, max_daily_minutes,
        min_break_minutes.
    existing_blocks : list[dict]
        Previously scheduled blocks.  Locked / completed ones are kept.
    projects : list[dict] | None
        Project metadata used for tag derivation.
    horizon_days : int
        How many days into the future to consider.

    Returns
    -------
    (new_blocks, unscheduled)
        new_blocks : list[dict]  – all blocks (commitments + placed tasks)
        unscheduled : list[dict] – tasks that could not be placed
    """
    project_map = {p["id"]: p for p in (projects or [])}
    today = date.today()
    horizon_end = today + timedelta(days=horizon_days)

    # --- Settings with defaults ---
    working_days = set(settings.get("working_days", [0, 1, 2, 3, 4, 5]))
    wh_start_str = settings.get("working_start", "09:00")
    wh_end_str = settings.get("working_end", "18:00")
    max_daily = settings.get("max_daily_minutes", 480)
    min_break = settings.get("min_break_minutes", 15)

    wh_s_h, wh_s_m = parse_time(wh_start_str)
    wh_e_h, wh_e_m = parse_time(wh_end_str)

    # ------------------------------------------------------------------
    # 1. Build commitment intervals over the horizon
    # ------------------------------------------------------------------
    commitment_intervals = generate_commitment_blocks(commitments, today, horizon_end)

    # ------------------------------------------------------------------
    # 2. Build locked/completed existing block intervals
    # ------------------------------------------------------------------
    locked_intervals = []
    for b in existing_blocks:
        b_start = parse_dt(b["start_dt"])
        # Locked, completed and skipped blocks are immovable records; past
        # blocks are preserved too so apply/regenerations don't resurrect them.
        if b.get("locked") or b.get("status") in ("completed", "skipped") or (b_start and b_start.date() < today):
            locked_intervals.append({
                "start": b_start,
                "end": parse_dt(b["end_dt"]),
                "locked": True,
                "title": b["title"],
                "tag": b.get("tag", ""),
                "task_id": b.get("task_id"),
                "commitment_id": b.get("commitment_id"),
                "reason": b.get("reason", ""),
                "status": b.get("status", "scheduled"),
            })

    # Fixed commitment blocks as interval dicts
    fixed_intervals = []
    for iv in commitment_intervals:
        fixed_intervals.append({
            "start": iv["start"],
            "end": iv["end"],
            "locked": True,
            "title": iv["title"],
            "tag": iv["tag"],
            "commitment_id": iv["commitment_id"],
            "status": "scheduled",
            "reason": "Fixed commitment",
        })

    # All immovable intervals (used for conflict detection)
    all_blocked = locked_intervals + fixed_intervals

    # ------------------------------------------------------------------
    # 3. Pre-compute daily capacity used by commitments (Rule 10)
    # ------------------------------------------------------------------
    daily_used = defaultdict(int)
    for iv in all_blocked:
        d = iv["start"].date()
        mins = int((iv["end"] - iv["start"]).total_seconds() / 60)
        daily_used[d] += mins

    # Index commitment titles by date for diagnostics
    commitment_titles_by_date = defaultdict(list)
    for iv in fixed_intervals:
        commitment_titles_by_date[iv["start"].date()].append(
            f"{iv['title']} {iv['start'].strftime('%H:%M')}–{iv['end'].strftime('%H:%M')}"
        )

    # ------------------------------------------------------------------
    # 4. Placed sessions (new task blocks)
    # ------------------------------------------------------------------
    placed = []  # list of interval dicts

    # Track the latest end time of any *placed* session per day for break
    # enforcement (Rule 9).  Keyed by date → latest end datetime on that date.
    # NOTE: deliberately NOT seeded from blocked intervals here — that pushed
    # the cursor past morning gaps before the first block of the day (G1).
    day_last_end = {}

    def _update_day_last_end(d, end_dt):
        """Update the latest session end time for *d*."""
        if d not in day_last_end or end_dt > day_last_end[d]:
            day_last_end[d] = end_dt

    # ------------------------------------------------------------------
    # Conflict & capacity helpers
    # ------------------------------------------------------------------
    def conflicts(start, end):
        """Return list of titles that conflict with [start, end).  Empty = no conflict."""
        hits = []
        for iv in all_blocked + placed:
            if start < iv["end"] and end > iv["start"]:
                hits.append(iv.get("title", "unknown"))
        return hits

    def daily_ok(d, extra_mins):
        """Can we add *extra_mins* of work to date *d* without exceeding max_daily?"""
        return daily_used[d] + extra_mins <= max_daily

    # ------------------------------------------------------------------
    # Slot finder (core of the engine)
    # ------------------------------------------------------------------
    def find_slot(task, session_minutes, earliest_dt, preferred_days, deadline_dt):
        """Find the earliest free slot for *session_minutes* on or after *earliest_dt*.

        Performs two passes:
          1. Only on preferred days
          2. On any working day

        Returns ``(start_dt, end_dt, day_date)`` or ``None``.
        """
        passes = []
        if preferred_days:
            passes.append(set(preferred_days))
        passes.append(None)  # any working day

        pref_start_str = task.get("preferred_start")
        pref_end_str = task.get("preferred_end")
        ps_h, ps_m = parse_time(pref_start_str) if pref_start_str else (wh_s_h, wh_s_m)
        pe_h, pe_m = parse_time(pref_end_str) if pref_end_str else (wh_e_h, wh_e_m)

        for pset in passes:
            # Start scanning from earliest_dt's date (but not before today)
            scan_date = max(earliest_dt.date(), today) if isinstance(earliest_dt, datetime) else max(earliest_dt, today)
            while scan_date <= horizon_end:
                # Rule 2: respect working days
                if scan_date.weekday() not in working_days:
                    scan_date += timedelta(days=1)
                    continue
                # Preferred-day filter (pass 1 only)
                if pset is not None and scan_date.weekday() not in pset:
                    scan_date += timedelta(days=1)
                    continue
                # Rule 3: slot must end before deadline
                if deadline_dt and datetime(scan_date.year, scan_date.month, scan_date.day, wh_e_h, wh_e_m) > deadline_dt:
                    # Day is past deadline — stop this pass
                    if datetime(scan_date.year, scan_date.month, scan_date.day, wh_s_h, wh_s_m) >= deadline_dt:
                        break
                # Rule 10: daily capacity check (quick pre-check)
                if not daily_ok(scan_date, session_minutes):
                    scan_date += timedelta(days=1)
                    continue

                def free_intervals(d):
                    """Free (start, end) intervals on day *d* within the working
                    window, after subtracting every blocked / already-placed
                    interval.  This makes gaps before the first block of the day
                    (and between blocks) reachable instead of being skipped
                    behind a single ``day_last_end`` pointer (G1)."""
                    day_start = datetime(d.year, d.month, d.day, wh_s_h, wh_s_m)
                    day_end = datetime(d.year, d.month, d.day, wh_e_h, wh_e_m)
                    ws = max(day_start, datetime(d.year, d.month, d.day, ps_h, ps_m))
                    we = min(day_end, datetime(d.year, d.month, d.day, pe_h, pe_m))
                    if we <= ws:
                        return []
                    blocked = []
                    for iv in all_blocked + placed:
                        s = max(iv["start"], ws)
                        e = min(iv["end"], we)
                        if e > s:
                            blocked.append((s, e))
                    blocked.sort()
                    free = []
                    cursor = ws
                    for s, e in blocked:
                        if s > cursor:
                            free.append((cursor, s))
                        cursor = max(cursor, e)
                    if cursor < we:
                        free.append((cursor, we))
                    return free

                day_wh_start = datetime(scan_date.year, scan_date.month, scan_date.day, wh_s_h, wh_s_m)
                day_wh_end = datetime(scan_date.year, scan_date.month, scan_date.day, wh_e_h, wh_e_m)
                pref_day_start = datetime(scan_date.year, scan_date.month, scan_date.day, ps_h, ps_m)
                pref_day_end = datetime(scan_date.year, scan_date.month, scan_date.day, pe_h, pe_m)
                cand_limit = min(day_wh_end, pref_day_end)
                # Clamp by deadline if deadline is on this day
                if deadline_dt and deadline_dt.date() == scan_date:
                    cand_limit = min(cand_limit, deadline_dt)

                latest_start = cand_limit - timedelta(minutes=session_minutes)
                if latest_start < day_wh_start:
                    # Day cannot fit a session at all
                    scan_date += timedelta(days=1)
                    continue

                for fs, fe in free_intervals(scan_date):
                    slot_start = fs
                    # If earliest_dt is a datetime on this same day, respect it
                    if isinstance(earliest_dt, datetime) and earliest_dt.date() == scan_date:
                        slot_start = max(slot_start, earliest_dt)
                    # Rule 9: break after last placed session on this day
                    if scan_date in day_last_end:
                        slot_start = max(slot_start, day_last_end[scan_date] + timedelta(minutes=min_break))
                    fe_clamped = min(fe, cand_limit)
                    ls = fe_clamped - timedelta(minutes=session_minutes)
                    if slot_start > ls:
                        continue

                    # Scan in 5-minute increments for a free slot
                    cur_t = slot_start
                    while cur_t <= ls:
                        s = cur_t
                        e = s + timedelta(minutes=session_minutes)
                        # Rule 3: must finish before deadline
                        if deadline_dt and e > deadline_dt:
                            break
                        hit = conflicts(s, e)
                        if not hit and daily_ok(scan_date, session_minutes):
                            return s, e, scan_date
                        # Advance past the conflict end to avoid wasting iterations
                        if hit:
                            conflict_end = max(
                                iv["end"] for iv in all_blocked + placed
                                if s < iv["end"] and e > iv["start"]
                            )
                            cur_t = conflict_end
                            cur_t = max(cur_t, conflict_end + timedelta(minutes=min_break))
                        else:
                            cur_t += timedelta(minutes=5)

                scan_date += timedelta(days=1)

        return None

    # ------------------------------------------------------------------
    # 5. Sort tasks (topo + deadline + priority)  — Rules 4, 5
    # ------------------------------------------------------------------
    sorted_tasks = topo_sort(tasks)

    # Track where each task's last session ends (full datetime for Rule 5)
    task_last_end = {}
    unscheduled = []

    # ------------------------------------------------------------------
    # 6. Place each task
    # ------------------------------------------------------------------
    for t in sorted_tasks:
        # Skip already-done tasks
        if t.get("status") == "done":
            continue

        remaining = t.get("remaining_minutes", 0) or 0
        if remaining <= 0:
            continue

        # --- Session splitting (Rules 7, 8) ---
        sessions = split_sessions(t)
        if not sessions:
            continue

        # --- Dependency earliest start (Rule 5: use full datetime) ---
        earliest_dt = datetime(today.year, today.month, today.day, wh_s_h, wh_s_m)
        dep_ok = True
        missing_deps = []
        for dep_id in (t.get("dependencies") or []):
            dep_task = next((x for x in tasks if x["id"] == dep_id), None)
            if dep_id in task_last_end:
                # Can start after prerequisite's last session ENDS (datetime).
                # Rule 12: a non-splittable prerequisite spreads work to the next
                # working day so chained single-session tasks don't pack onto
                # the same day (one block per preferred day).
                dep_end = task_last_end[dep_id]
                earliest_dt = max(earliest_dt, dep_end)
                if dep_task and not dep_task.get("splittable", True):
                    earliest_dt = max(
                        earliest_dt,
                        datetime(dep_end.year, dep_end.month, dep_end.day, wh_s_h, wh_s_m) + timedelta(days=1),
                    )
            elif dep_task and dep_task.get("status") == "done":
                # Already completed — no constraint
                pass
            elif dep_task:
                dep_ok = False
                missing_deps.append(dep_task.get("title", str(dep_id)))
            # If dep_task is None the dependency references an unknown task;
            # treat as satisfied (defensive).

        if not dep_ok:
            reason = _build_unscheduled_reason(
                t,
                f"Cannot schedule: prerequisite(s) not scheduled ({', '.join(missing_deps)}).",
            )
            unscheduled.append({"task_id": t["id"], "title": t["title"], "reason": reason})
            continue

        # --- Deadline ---
        deadline_dt = None
        if t.get("deadline"):
            dl_date = parse_date(t["deadline"])
            # Interpret deadline as end-of-day unless a time component is given
            if "T" in str(t["deadline"]):
                deadline_dt = parse_dt(t["deadline"])
            else:
                deadline_dt = datetime(dl_date.year, dl_date.month, dl_date.day,
                                       wh_e_h, wh_e_m)

        preferred_days = t.get("preferred_days") or []

        # --- Place each session (Rule 12: spread across days) ---
        cur_earliest = earliest_dt
        all_ok = True
        last_end = None
        placed_for_task = []
        available_before_deadline = None  # for diagnostics if we fail

        for si, dur in enumerate(sessions):
            result = find_slot(t, dur, cur_earliest, preferred_days, deadline_dt)
            if result is None and preferred_days:
                # Retry without preferred-day constraint
                result = find_slot(t, dur, cur_earliest, [], deadline_dt)
            if result is None:
                all_ok = False
                break
            s, e, day = result

            reason = _build_placement_reason(
                t, s, e, preferred_days,
                commitment_titles_by_date.get(day),
            )
            block = {
                "start": s,
                "end": e,
                "task_id": t["id"],
                "title": t["title"],
                "tag": tag_for_task(t, project_map),
                "locked": False,
                "status": "scheduled",
                "reason": reason,
            }
            placed.append(block)
            placed_for_task.append(block)
            daily_used[day] += dur
            _update_day_last_end(day, e)
            last_end = e

            # Rule 12 — advance earliest to next day to spread work.
            if si < len(sessions) - 1:
                cur_earliest = datetime(day.year, day.month, day.day, wh_s_h, wh_s_m) + timedelta(days=1)
            else:
                # Same day is fine, break gap handled by find_slot
                cur_earliest = e

        if all_ok and last_end is not None:
            task_last_end[t["id"]] = last_end
        elif not all_ok:
            # Roll back any sessions placed for this task
            placed_ids = {id(p) for p in placed_for_task}
            for pf in placed_for_task:
                d = pf["start"].date()
                dur = int((pf["end"] - pf["start"]).total_seconds() / 60)
                daily_used[d] -= dur
            placed = [p for p in placed if id(p) not in placed_ids]

            # Compute available minutes before deadline for diagnostics
            blocking = []
            if deadline_dt:
                avail = _compute_available_minutes(
                    earliest_dt, deadline_dt, working_days,
                    wh_s_h, wh_s_m, wh_e_h, wh_e_m,
                    all_blocked + placed, max_daily, daily_used,
                )
                available_before_deadline = avail
                # Collect blocking commitments
                for iv in fixed_intervals:
                    if iv["start"] < deadline_dt and iv["end"] > earliest_dt:
                        blocking.append(
                            f"{iv['title']} {iv['start'].strftime('%a %H:%M')}–{iv['end'].strftime('%H:%M')}"
                        )

            detail = (
                f"Deadline {t['deadline']} cannot be met."
                if t.get("deadline")
                else "Not enough available time within the scheduling horizon."
            )
            reason = _build_unscheduled_reason(
                t, detail,
                blocking_commitments=blocking or None,
                available_minutes=available_before_deadline,
            )
            unscheduled.append({"task_id": t["id"], "title": t["title"], "reason": reason})

    # ------------------------------------------------------------------
    # 7. Build output blocks
    # ------------------------------------------------------------------
    new_blocks = []

    # Include fixed/locked intervals
    for iv in all_blocked:
        new_blocks.append({
            "task_id": iv.get("task_id"),
            "commitment_id": iv.get("commitment_id"),
            "title": iv["title"],
            "tag": iv.get("tag", ""),
            "start_dt": fmt_dt(iv["start"]),
            "end_dt": fmt_dt(iv["end"]),
            "status": iv.get("status", "scheduled"),
            "locked": True,
            "reason": iv.get("reason", ""),
        })

    # Include newly placed task sessions
    for p in placed:
        new_blocks.append({
            "task_id": p["task_id"],
            "commitment_id": None,
            "title": p["title"],
            "tag": p["tag"],
            "start_dt": fmt_dt(p["start"]),
            "end_dt": fmt_dt(p["end"]),
            "status": "scheduled",
            "locked": False,
            "reason": p["reason"],
        })

    return new_blocks, unscheduled


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_available_minutes(earliest_dt, deadline_dt, working_days,
                               wh_s_h, wh_s_m, wh_e_h, wh_e_m,
                               blocked_intervals, max_daily, daily_used):
    """Estimate total available working minutes between *earliest_dt* and
    *deadline_dt*, accounting for blocked intervals and daily caps.

    Used purely for diagnostic messages when a task cannot be placed.
    """
    total = 0
    d = earliest_dt.date()
    end_d = deadline_dt.date()
    while d <= end_d:
        if d.weekday() not in working_days:
            d += timedelta(days=1)
            continue
        day_start = datetime(d.year, d.month, d.day, wh_s_h, wh_s_m)
        day_end = datetime(d.year, d.month, d.day, wh_e_h, wh_e_m)
        if d == earliest_dt.date():
            day_start = max(day_start, earliest_dt)
        if d == deadline_dt.date():
            day_end = min(day_end, deadline_dt)
        if day_end <= day_start:
            d += timedelta(days=1)
            continue

        day_total = int((day_end - day_start).total_seconds() / 60)
        # Subtract blocked intervals on this day
        for iv in blocked_intervals:
            if iv["start"].date() != d:
                continue
            ov_start = max(iv["start"], day_start)
            ov_end = min(iv["end"], day_end)
            if ov_end > ov_start:
                day_total -= int((ov_end - ov_start).total_seconds() / 60)
        # Respect daily cap
        already_used = daily_used.get(d, 0)
        remaining_cap = max(0, max_daily - already_used)
        total += min(day_total, remaining_cap)
        d += timedelta(days=1)
    return max(total, 0)
