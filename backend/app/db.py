import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import DB_PATH, DEFAULT_SETTINGS

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    kind TEXT DEFAULT 'project',
    total_sessions INTEGER DEFAULT 0,
    session_minutes INTEGER DEFAULT 60,
    target_deadline TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    estimated_minutes INTEGER DEFAULT 60,
    remaining_minutes INTEGER DEFAULT 60,
    deadline TEXT,
    priority INTEGER DEFAULT 3,
    preferred_days TEXT DEFAULT '[]',
    preferred_start TEXT,
    preferred_end TEXT,
    min_session_minutes INTEGER DEFAULT 25,
    max_session_minutes INTEGER DEFAULT 90,
    splittable INTEGER DEFAULT 1,
    flexible INTEGER DEFAULT 1,
    dependencies TEXT DEFAULT '[]',
    status TEXT DEFAULT 'todo',
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS commitments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    kind TEXT DEFAULT 'fixed',
    tag TEXT DEFAULT 'personal',
    recurrence TEXT DEFAULT 'weekly',
    days_of_week TEXT DEFAULT '[]',
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    one_time_date TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS schedule_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    commitment_id INTEGER,
    title TEXT NOT NULL,
    tag TEXT DEFAULT 'task',
    start_dt TEXT NOT NULL,
    end_dt TEXT NOT NULL,
    status TEXT DEFAULT 'scheduled',
    locked INTEGER DEFAULT 0,
    reason TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    FOREIGN KEY(commitment_id) REFERENCES commitments(id) ON DELETE CASCADE
);
"""

@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
        row = conn.execute("SELECT id FROM settings WHERE id=1").fetchone()
        if not row:
            conn.execute("INSERT INTO settings(id,data) VALUES(1,?)", (json.dumps(DEFAULT_SETTINGS),))

def get_settings():
    with connect() as conn:
        row = conn.execute("SELECT data FROM settings WHERE id=1").fetchone()
        data = json.loads(row["data"])
        merged = {**DEFAULT_SETTINGS, **data}
        return merged

def save_settings(s):
    with connect() as conn:
        conn.execute("UPDATE settings SET data=? WHERE id=1", (json.dumps(s),))

def now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def row_to_dict(r):
    return dict(r) if r else None

# Generic helpers
def list_projects():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

def get_project(pid):
    with connect() as conn:
        r = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        return dict(r) if r else None

def create_project(data):
    ts = now_iso()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO projects(name,description,kind,total_sessions,session_minutes,target_deadline,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (data["name"], data.get("description",""), data.get("kind","project"),
             data.get("total_sessions",0), data.get("session_minutes",60),
             data.get("target_deadline"), ts, ts))
        new_id = cur.lastrowid
    return get_project(new_id)

def update_project(pid, data):
    ts = now_iso()
    fields = []
    vals = []
    for k in ["name","description","kind","total_sessions","session_minutes","target_deadline"]:
        if k in data and data[k] is not None:
            fields.append(f"{k}=?")
            vals.append(data[k])
    if not fields:
        return get_project(pid)
    fields.append("updated_at=?")
    vals.append(ts)
    vals.append(pid)
    with connect() as conn:
        conn.execute(f"UPDATE projects SET {','.join(fields)} WHERE id=?", vals)
    return get_project(pid)

def delete_project(pid):
    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE id=?", (pid,))

def list_tasks(project_id=None, status=None):
    q = "SELECT * FROM tasks"
    params = []
    conds = []
    if project_id is not None:
        conds.append("project_id=?"); params.append(project_id)
    if status:
        conds.append("status=?"); params.append(status)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY id DESC"
    with connect() as conn:
        rows = conn.execute(q, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["preferred_days"] = json.loads(d["preferred_days"] or "[]")
            d["dependencies"] = json.loads(d["dependencies"] or "[]")
            out.append(d)
        return out

def get_task(tid):
    with connect() as conn:
        r = conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        if not r: return None
        d = dict(r)
        d["preferred_days"] = json.loads(d["preferred_days"] or "[]")
        d["dependencies"] = json.loads(d["dependencies"] or "[]")
        return d

def create_task(data):
    ts = now_iso()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO tasks(project_id,title,description,estimated_minutes,remaining_minutes,deadline,priority,preferred_days,preferred_start,preferred_end,min_session_minutes,max_session_minutes,splittable,flexible,dependencies,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (data.get("project_id"), data["title"], data.get("description",""),
             data.get("estimated_minutes",60), data.get("remaining_minutes", data.get("estimated_minutes",60)),
             data.get("deadline"), data.get("priority",3),
             json.dumps(data.get("preferred_days",[])), data.get("preferred_start"), data.get("preferred_end"),
             data.get("min_session_minutes",25), data.get("max_session_minutes",90),
             1 if data.get("splittable",True) else 0, 1 if data.get("flexible",True) else 0,
             json.dumps(data.get("dependencies",[])), data.get("status","todo"), ts, ts))
        new_id = cur.lastrowid
    return get_task(new_id)

def update_task(tid, data):
    ts = now_iso()
    simple = ["project_id","title","description","estimated_minutes","remaining_minutes","deadline","priority","preferred_start","preferred_end","min_session_minutes","max_session_minutes","status","completed_at"]
    fields=[]; vals=[]
    for k in simple:
        if k in data:
            fields.append(f"{k}=?"); vals.append(data[k])
    if "preferred_days" in data:
        fields.append("preferred_days=?"); vals.append(json.dumps(data["preferred_days"]))
    if "dependencies" in data:
        fields.append("dependencies=?"); vals.append(json.dumps(data["dependencies"]))
    if "splittable" in data:
        fields.append("splittable=?"); vals.append(1 if data["splittable"] else 0)
    if "flexible" in data:
        fields.append("flexible=?"); vals.append(1 if data["flexible"] else 0)
    if not fields:
        return get_task(tid)
    fields.append("updated_at=?"); vals.append(ts); vals.append(tid)
    with connect() as conn:
        conn.execute(f"UPDATE tasks SET {','.join(fields)} WHERE id=?", vals)
    return get_task(tid)

def delete_task(tid):
    with connect() as conn:
        conn.execute("DELETE FROM tasks WHERE id=?", (tid,))

def list_commitments(tag=None):
    q = "SELECT * FROM commitments"
    params = []
    if tag:
        q += " WHERE tag = ?"
        params.append(tag)
    q += " ORDER BY id DESC"
    with connect() as conn:
        rows = conn.execute(q, params).fetchall()
        out=[]
        for r in rows:
            d=dict(r)
            d["days_of_week"]=json.loads(d["days_of_week"] or "[]")
            out.append(d)
        return out

def get_commitment(cid):
    with connect() as conn:
        r = conn.execute("SELECT * FROM commitments WHERE id=?", (cid,)).fetchone()
        if not r: return None
        d=dict(r); d["days_of_week"]=json.loads(d["days_of_week"] or "[]")
        return d

def create_commitment(data):
    ts = now_iso()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO commitments(title,kind,tag,recurrence,days_of_week,start_time,end_time,start_date,end_date,one_time_date,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (data["title"], data.get("kind","fixed"), data.get("tag","personal"),
             data.get("recurrence","weekly"), json.dumps(data.get("days_of_week",[])),
             data["start_time"], data["end_time"], data.get("start_date"), data.get("end_date"),
             data.get("one_time_date"), ts, ts))
        new_id = cur.lastrowid
    return get_commitment(new_id)

def update_commitment(cid, data):
    ts = now_iso()
    fields=[]; vals=[]
    for k in ["title","kind","tag","recurrence","start_time","end_time","start_date","end_date","one_time_date"]:
        if k in data:
            fields.append(f"{k}=?"); vals.append(data[k])
    if "days_of_week" in data:
        fields.append("days_of_week=?"); vals.append(json.dumps(data["days_of_week"]))
    if not fields:
        return get_commitment(cid)
    fields.append("updated_at=?"); vals.append(ts); vals.append(cid)
    with connect() as conn:
        conn.execute(f"UPDATE commitments SET {','.join(fields)} WHERE id=?", vals)
    return get_commitment(cid)

def delete_commitment(cid):
    with connect() as conn:
        conn.execute("DELETE FROM commitments WHERE id=?", (cid,))

def list_blocks(start=None, end=None):
    q="SELECT * FROM schedule_blocks"
    params=[]; conds=[]
    if start:
        conds.append("end_dt >= ?"); params.append(start)
    if end:
        conds.append("start_dt <= ?"); params.append(end)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY start_dt"
    with connect() as conn:
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

def create_block(data):
    ts = now_iso()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO schedule_blocks(task_id,commitment_id,title,tag,start_dt,end_dt,status,locked,reason,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (data.get("task_id"), data.get("commitment_id"), data["title"], data.get("tag","task"),
             data["start_dt"], data["end_dt"], data.get("status","scheduled"),
             1 if data.get("locked",False) else 0, data.get("reason",""), ts, ts))
        r = conn.execute("SELECT * FROM schedule_blocks WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(r)

def update_block(bid, data):
    ts = now_iso()
    fields=[]; vals=[]
    for k in ["title","tag","start_dt","end_dt","status","reason"]:
        if k in data:
            fields.append(f"{k}=?"); vals.append(data[k])
    if "locked" in data:
        fields.append("locked=?"); vals.append(1 if data["locked"] else 0)
    if "task_id" in data:
        fields.append("task_id=?"); vals.append(data["task_id"])
    if not fields:
        return None
    fields.append("updated_at=?"); vals.append(ts); vals.append(bid)
    with connect() as conn:
        conn.execute(f"UPDATE schedule_blocks SET {','.join(fields)} WHERE id=?", vals)
        r = conn.execute("SELECT * FROM schedule_blocks WHERE id=?", (bid,)).fetchone()
        return dict(r) if r else None

def delete_block(bid):
    with connect() as conn:
        conn.execute("DELETE FROM schedule_blocks WHERE id=?", (bid,))

def delete_future_flexible_blocks(cutoff_iso):
    with connect() as conn:
        conn.execute("DELETE FROM schedule_blocks WHERE locked=0 AND status IN ('scheduled') AND start_dt >= ?", (cutoff_iso,))

def export_all():
    with connect() as conn:
        tables = ["settings","projects","tasks","commitments","schedule_blocks"]
        out={}
        for t in tables:
            rows = conn.execute(f"SELECT * FROM {t}").fetchall()
            out[t]=[dict(r) for r in rows]
        return out


def clear_all_data():
    """Delete all rows from every data table (order respects FK constraints)."""
    with connect() as conn:
        for table in ["schedule_blocks", "tasks", "projects", "commitments", "settings"]:
            conn.execute(f"DELETE FROM {table}")


def reset_db():
    """Clear all data and reinitialize settings to defaults."""
    clear_all_data()
    with connect() as conn:
        conn.execute(
            "INSERT INTO settings(id, data) VALUES(1, ?)",
            (json.dumps(DEFAULT_SETTINGS),),
        )


def import_all(payload: dict) -> dict:
    """Import data produced by export_all(). Clears existing data first.

    Args:
        payload: Dict with optional keys: settings, projects, tasks,
                 commitments, schedule_blocks — each a list of row dicts.

    Returns:
        Dict with counts of imported rows per table.
    """
    reset_db()
    counts: dict[str, int] = {}

    with connect() as conn:
        # --- settings ---
        settings_rows = payload.get("settings", [])
        if settings_rows:
            # The export stores settings as [{id:1, data: "..."}]
            for row in settings_rows:
                data_val = row.get("data", json.dumps(DEFAULT_SETTINGS))
                conn.execute("UPDATE settings SET data=? WHERE id=1", (data_val,))
            counts["settings"] = len(settings_rows)
        else:
            counts["settings"] = 0

        # --- projects ---
        for p in payload.get("projects", []):
            ts = p.get("created_at", now_iso())
            conn.execute(
                "INSERT INTO projects(id,name,description,kind,total_sessions,session_minutes,target_deadline,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (p.get("id"), p["name"], p.get("description", ""),
                 p.get("kind", "project"), p.get("total_sessions", 0),
                 p.get("session_minutes", 60), p.get("target_deadline"),
                 ts, p.get("updated_at", ts)),
            )
        counts["projects"] = len(payload.get("projects", []))

        # --- tasks ---
        for t in payload.get("tasks", []):
            ts = t.get("created_at", now_iso())
            pdays = t.get("preferred_days", "[]")
            if isinstance(pdays, list):
                pdays = json.dumps(pdays)
            deps = t.get("dependencies", "[]")
            if isinstance(deps, list):
                deps = json.dumps(deps)
            conn.execute(
                "INSERT INTO tasks(id,project_id,title,description,estimated_minutes,remaining_minutes,"
                "deadline,priority,preferred_days,preferred_start,preferred_end,"
                "min_session_minutes,max_session_minutes,splittable,flexible,"
                "dependencies,status,completed_at,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (t.get("id"), t.get("project_id"), t["title"], t.get("description", ""),
                 t.get("estimated_minutes", 60), t.get("remaining_minutes", t.get("estimated_minutes", 60)),
                 t.get("deadline"), t.get("priority", 3), pdays,
                 t.get("preferred_start"), t.get("preferred_end"),
                 t.get("min_session_minutes", 25), t.get("max_session_minutes", 90),
                 1 if t.get("splittable", True) else 0,
                 1 if t.get("flexible", True) else 0,
                 deps, t.get("status", "todo"), t.get("completed_at"),
                 ts, t.get("updated_at", ts)),
            )
        counts["tasks"] = len(payload.get("tasks", []))

        # --- commitments ---
        for c in payload.get("commitments", []):
            ts = c.get("created_at", now_iso())
            dow = c.get("days_of_week", "[]")
            if isinstance(dow, list):
                dow = json.dumps(dow)
            conn.execute(
                "INSERT INTO commitments(id,title,kind,tag,recurrence,days_of_week,"
                "start_time,end_time,start_date,end_date,one_time_date,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (c.get("id"), c["title"], c.get("kind", "fixed"), c.get("tag", "personal"),
                 c.get("recurrence", "weekly"), dow,
                 c["start_time"], c["end_time"], c.get("start_date"), c.get("end_date"),
                 c.get("one_time_date"), ts, c.get("updated_at", ts)),
            )
        counts["commitments"] = len(payload.get("commitments", []))

        # --- schedule_blocks ---
        for b in payload.get("schedule_blocks", []):
            ts = b.get("created_at", now_iso())
            conn.execute(
                "INSERT INTO schedule_blocks(id,task_id,commitment_id,title,tag,"
                "start_dt,end_dt,status,locked,reason,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (b.get("id"), b.get("task_id"), b.get("commitment_id"),
                 b["title"], b.get("tag", "task"),
                 b["start_dt"], b["end_dt"], b.get("status", "scheduled"),
                 1 if b.get("locked", False) else 0,
                 b.get("reason", ""), ts, b.get("updated_at", ts)),
            )
        counts["schedule_blocks"] = len(payload.get("schedule_blocks", []))

    return counts
