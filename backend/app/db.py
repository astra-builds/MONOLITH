import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
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
CREATE TABLE IF NOT EXISTS milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    deadline TEXT,
    sequence INTEGER DEFAULT 0,
    status TEXT DEFAULT 'todo',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS availability_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    weekday INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    available INTEGER DEFAULT 1,
    source TEXT DEFAULT 'user',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS planning_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    source TEXT NOT NULL DEFAULT 'offline',
    request_text TEXT NOT NULL,
    structured_plan_json TEXT NOT NULL,
    schedule_preview_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    approved_at TEXT
);
CREATE TABLE IF NOT EXISTS ai_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id INTEGER,
    operation_type TEXT NOT NULL,
    target_type TEXT,
    target_id INTEGER,
    arguments_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    result_json TEXT,
    error_message TEXT,
    idempotency_key TEXT UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(proposal_id) REFERENCES planning_proposals(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS ai_conversations (
    id TEXT PRIMARY KEY,
    messages_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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

def _json_column(value, default):
    if value in (None, ""):
        return default
    return json.loads(value)

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


def delete_project_tasks(pid):
    """Remove all tasks (and their schedule blocks via ON DELETE CASCADE)
    for a project, so a course can be regenerated idempotently (G3)."""
    with connect() as conn:
        conn.execute("DELETE FROM tasks WHERE project_id=?", (pid,))

# Canonical planning-domain helpers. These records are intentionally separate
# from the AI provider so proposals can be validated and previewed before any
# existing project/task/calendar data is changed.
def list_milestones(project_id=None):
    q = "SELECT * FROM milestones"
    params = []
    if project_id is not None:
        q += " WHERE project_id=?"
        params.append(project_id)
    q += " ORDER BY project_id, sequence, id"
    with connect() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]

def get_milestone(mid):
    with connect() as conn:
        row = conn.execute("SELECT * FROM milestones WHERE id=?", (mid,)).fetchone()
        return dict(row) if row else None

def create_milestone(data):
    ts = now_iso()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO milestones(project_id,title,description,deadline,sequence,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (data["project_id"], data["title"], data.get("description", ""),
             data.get("deadline"), data.get("sequence", 0), data.get("status", "todo"), ts, ts),
        )
        mid = cur.lastrowid
    return get_milestone(mid)

def update_milestone(mid, data):
    fields = []
    values = []
    for key in ["project_id", "title", "description", "deadline", "sequence", "status"]:
        if key in data:
            fields.append(f"{key}=?")
            values.append(data[key])
    if not fields:
        return get_milestone(mid)
    fields.append("updated_at=?")
    values.extend([now_iso(), mid])
    with connect() as conn:
        conn.execute(f"UPDATE milestones SET {','.join(fields)} WHERE id=?", values)
    return get_milestone(mid)

def delete_milestone(mid):
    with connect() as conn:
        conn.execute("DELETE FROM milestones WHERE id=?", (mid,))

def list_availability_rules():
    with connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM availability_rules ORDER BY weekday, start_time, id"
        ).fetchall()]

def create_availability_rule(data):
    ts = now_iso()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO availability_rules(weekday,start_time,end_time,available,source,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (data["weekday"], data["start_time"], data["end_time"],
             1 if data.get("available", True) else 0, data.get("source", "user"), ts, ts),
        )
        rid = cur.lastrowid
    with connect() as conn:
        return dict(conn.execute("SELECT * FROM availability_rules WHERE id=?", (rid,)).fetchone())

def delete_availability_rule(rid):
    with connect() as conn:
        conn.execute("DELETE FROM availability_rules WHERE id=?", (rid,))

def create_planning_proposal(data):
    ts = now_iso()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO planning_proposals(conversation_id,status,source,request_text,structured_plan_json,schedule_preview_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (data.get("conversation_id"), data.get("status", "draft"), data.get("source", "offline"),
             data["request_text"], json.dumps(data.get("structured_plan", {})),
             json.dumps(data["schedule_preview"]) if data.get("schedule_preview") is not None else None,
             ts, ts),
        )
        pid = cur.lastrowid
    return get_planning_proposal(pid)

def get_planning_proposal(pid):
    with connect() as conn:
        row = conn.execute("SELECT * FROM planning_proposals WHERE id=?", (pid,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["structured_plan"] = _json_column(result.pop("structured_plan_json"), {})
        result["schedule_preview"] = _json_column(result.pop("schedule_preview_json"), None)
        return result

def update_planning_proposal(pid, data):
    fields = []
    values = []
    for key in ["conversation_id", "status", "source", "request_text", "approved_at"]:
        if key in data:
            fields.append(f"{key}=?")
            values.append(data[key])
    if "structured_plan" in data:
        fields.append("structured_plan_json=?")
        values.append(json.dumps(data["structured_plan"]))
    if "schedule_preview" in data:
        fields.append("schedule_preview_json=?")
        values.append(json.dumps(data["schedule_preview"]))
    if not fields:
        return get_planning_proposal(pid)
    fields.append("updated_at=?")
    values.extend([now_iso(), pid])
    with connect() as conn:
        conn.execute(f"UPDATE planning_proposals SET {','.join(fields)} WHERE id=?", values)
    return get_planning_proposal(pid)

def create_ai_operation(data):
    ts = now_iso()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO ai_operations(proposal_id,operation_type,target_type,target_id,arguments_json,status,result_json,error_message,idempotency_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (data.get("proposal_id"), data["operation_type"], data.get("target_type"), data.get("target_id"),
             json.dumps(data.get("arguments", {})), data.get("status", "pending"),
             json.dumps(data["result"]) if data.get("result") is not None else None,
             data.get("error_message"), data.get("idempotency_key"), ts, ts),
        )
        oid = cur.lastrowid
    with connect() as conn:
        row = conn.execute("SELECT * FROM ai_operations WHERE id=?", (oid,)).fetchone()
        result = dict(row)
        result["arguments"] = _json_column(result.pop("arguments_json"), {})
        result["result"] = _json_column(result.pop("result_json"), None)
        return result

def get_ai_operation_by_key(key):
    with connect() as conn:
        row = conn.execute("SELECT * FROM ai_operations WHERE idempotency_key=?", (key,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["arguments"] = _json_column(result.pop("arguments_json"), {})
        result["result"] = _json_column(result.pop("result_json"), None)
        return result

def get_conversation(conversation_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM ai_conversations WHERE id=?", (conversation_id,)).fetchone()
        if not row:
            return {"id": conversation_id, "messages": []}
        result = dict(row)
        result["messages"] = _json_column(result.pop("messages_json"), [])
        return result

def save_conversation(conversation_id, messages):
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            "INSERT INTO ai_conversations(id,messages_json,created_at,updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET messages_json=excluded.messages_json, updated_at=excluded.updated_at",
            (conversation_id, json.dumps(messages), ts, ts),
        )
    return get_conversation(conversation_id)

def apply_planning_proposal_transaction(proposal_id, intent, preview_blocks):
    """Apply a validated plan and its schedule in one SQLite transaction.

    Preview-only negative IDs are translated to real IDs here. Existing fixed,
    completed, skipped, and past blocks remain immutable and are never deleted.
    """
    ts = now_iso()
    project_map = {}
    task_map = {}
    commitment_map = {}
    created = {"projects": [], "milestones": [], "tasks": [], "commitments": [], "blocks": []}

    with connect() as conn:
        row = conn.execute("SELECT status FROM planning_proposals WHERE id=?", (proposal_id,)).fetchone()
        if not row or row["status"] not in ("draft", "previewed"):
            raise ValueError("Planning proposal is no longer applicable")

        existing_projects = {
            row["name"].casefold(): dict(row)
            for row in conn.execute("SELECT * FROM projects").fetchall()
        }
        for project in intent.get("projects", []):
            name = project["name"]
            existing = existing_projects.get(name.casefold())
            if existing:
                project_map[name.casefold()] = existing["id"]
                continue
            cur = conn.execute(
                "INSERT INTO projects(name,description,kind,total_sessions,session_minutes,target_deadline,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (name, project.get("description", ""), project.get("kind", "project"),
                 project.get("total_sessions", 0), project.get("session_minutes", 60),
                 project.get("target_deadline"), ts, ts),
            )
            project_map[name.casefold()] = cur.lastrowid
            created["projects"].append({"id": cur.lastrowid, "name": name})

        for project in intent.get("projects", []):
            project_id = project_map[project["name"].casefold()]
            for milestone in project.get("milestones", []):
                cur = conn.execute(
                    "INSERT INTO milestones(project_id,title,description,deadline,sequence,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                    (project_id, milestone["title"], milestone.get("description", ""), milestone.get("deadline"),
                     milestone.get("sequence", 0), "todo", ts, ts),
                )
                created["milestones"].append({"id": cur.lastrowid, "project_id": project_id, "title": milestone["title"]})

        raw_tasks = []
        for project in intent.get("projects", []):
            raw_tasks.extend([{**task, "project_name": project["name"]} for task in project.get("tasks", [])])
        raw_tasks.extend(intent.get("tasks", []))
        previous_task_id = None
        for task in raw_tasks:
            project_id = project_map.get((task.get("project_name") or "").casefold())
            dependencies = []
            for dependency in task.get("dependencies", []):
                if dependency == "__PREV__" and previous_task_id is not None:
                    dependencies.append(previous_task_id)
                elif isinstance(dependency, int):
                    dependencies.append(dependency)
                elif isinstance(dependency, str) and dependency.casefold() in task_map:
                    dependencies.append(task_map[dependency.casefold()])
            cur = conn.execute(
                "INSERT INTO tasks(project_id,title,description,estimated_minutes,remaining_minutes,deadline,priority,preferred_days,preferred_start,preferred_end,min_session_minutes,max_session_minutes,splittable,flexible,dependencies,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (project_id, task["title"], task.get("description", ""), task.get("estimated_minutes", 60),
                 task.get("estimated_minutes", 60), task.get("deadline"), task.get("priority", 3),
                 json.dumps(task.get("preferred_days", [])), task.get("preferred_start"), task.get("preferred_end"),
                 task.get("min_session_minutes", 25), task.get("max_session_minutes", 90),
                 1 if task.get("splittable", True) else 0, 1 if task.get("flexible", True) else 0,
                 json.dumps(dependencies), "todo", ts, ts),
            )
            task_map[task["title"].casefold()] = cur.lastrowid
            previous_task_id = cur.lastrowid
            created["tasks"].append({"id": cur.lastrowid, "title": task["title"], "project_id": project_id})

        for commitment in intent.get("commitments", []):
            cur = conn.execute(
                "INSERT INTO commitments(title,kind,tag,recurrence,days_of_week,start_time,end_time,start_date,end_date,one_time_date,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (commitment["title"], commitment.get("kind", "fixed"), commitment.get("tag", "personal"),
                 commitment.get("recurrence", "weekly"), json.dumps(commitment.get("days_of_week", [])),
                 commitment["start_time"], commitment["end_time"], commitment.get("start_date"),
                 commitment.get("end_date"), commitment.get("one_time_date"), ts, ts),
            )
            commitment_map[commitment.get("title", "").casefold()] = cur.lastrowid
            created["commitments"].append({"id": cur.lastrowid, "title": commitment["title"]})

        now_local = datetime.now().replace(microsecond=0).isoformat()
        preserved_rows = conn.execute("SELECT * FROM schedule_blocks").fetchall()
        preserved = []
        for old in preserved_rows:
            old_dict = dict(old)
            start = old_dict["start_dt"]
            if old_dict["locked"] or old_dict["status"] in ("completed", "skipped") or start < now_local[:10]:
                preserved.append(old_dict)
        conn.execute(
            "DELETE FROM schedule_blocks WHERE locked=0 AND status='scheduled' AND start_dt >= ?",
            (now_local,),
        )
        existing_keys = {(b["start_dt"], b["end_dt"], b["title"]) for b in preserved}
        for block in preview_blocks:
            task_id = block.get("task_id")
            commitment_id = block.get("commitment_id")
            if task_id is not None and task_id < 0:
                # Preview task IDs are assigned in insertion order; resolve by title.
                task_id = task_map.get(block["title"].casefold())
            if commitment_id is not None and commitment_id < 0:
                commitment_id = commitment_map.get(block["title"].casefold())
            if task_id is None and commitment_id is None:
                continue
            key = (block["start_dt"], block["end_dt"], block["title"])
            if key in existing_keys:
                continue
            conn.execute(
                "INSERT INTO schedule_blocks(task_id,commitment_id,title,tag,start_dt,end_dt,status,locked,reason,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (task_id, commitment_id, block["title"], block.get("tag", "task"), block["start_dt"],
                 block["end_dt"], block.get("status", "scheduled"), 1 if block.get("locked") else 0,
                 block.get("reason", ""), ts, ts),
            )
            created["blocks"].append({"title": block["title"], "start_dt": block["start_dt"], "end_dt": block["end_dt"]})

        conn.execute(
            "UPDATE planning_proposals SET status='approved', approved_at=?, updated_at=? WHERE id=?",
            (ts, ts, proposal_id),
        )
        conn.execute(
            "INSERT INTO ai_operations(proposal_id,operation_type,target_type,target_id,arguments_json,status,result_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (proposal_id, "approve_proposal", "planning_proposal", proposal_id, json.dumps({"proposal_id": proposal_id}),
             "success", json.dumps(created), ts, ts),
        )
    return created

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
        # Editing a commitment must not leave stale locked blocks at the old
        # time — drop future locked blocks for this commitment so the next
        # regeneration rebuilds them at the new time (G5).
        conn.execute(
            "DELETE FROM schedule_blocks WHERE commitment_id=? AND locked=1 AND start_dt >= ?",
            (cid, datetime.now().replace(microsecond=0).isoformat()),
        )
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
        tables = ["settings","projects","milestones","tasks","commitments","availability_rules","schedule_blocks"]
        out={}
        for t in tables:
            rows = conn.execute(f"SELECT * FROM {t}").fetchall()
            out[t]=[dict(r) for r in rows]
        # Never embed AI API key material in an exported snapshot (instructions.txt:265).
        for row in out.get("settings", []):
            try:
                data = json.loads(row.get("data", "{}"))
            except Exception:
                data = {}
            if data.get("ai_api_key"):
                data["ai_api_key"] = "********"
            row["data"] = json.dumps(data)
        return out


def clear_all_data():
    """Delete all rows from every data table (order respects FK constraints)."""
    with connect() as conn:
        for table in ["ai_operations", "ai_conversations", "schedule_blocks", "tasks", "milestones", "projects", "commitments", "availability_rules", "planning_proposals", "settings"]:
            conn.execute(f"DELETE FROM {table}")


def reset_db():
    """Clear all data and reinitialize settings to defaults."""
    init_db()  # ensure tables exist on a fresh DB
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

        # --- milestones ---
        for m in payload.get("milestones", []):
            ts = m.get("created_at", now_iso())
            conn.execute(
                "INSERT INTO milestones(id,project_id,title,description,deadline,sequence,status,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (m.get("id"), m.get("project_id"), m["title"], m.get("description", ""),
                 m.get("deadline"), m.get("sequence", 0), m.get("status", "todo"), ts, m.get("updated_at", ts)),
            )
        counts["milestones"] = len(payload.get("milestones", []))

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

        # --- availability_rules ---
        for r in payload.get("availability_rules", []):
            ts = r.get("created_at", now_iso())
            conn.execute(
                "INSERT INTO availability_rules(id,weekday,start_time,end_time,available,source,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (r.get("id"), r.get("weekday"), r["start_time"], r["end_time"],
                 1 if r.get("available", True) else 0, r.get("source", "user"), ts, r.get("updated_at", ts)),
            )
        counts["availability_rules"] = len(payload.get("availability_rules", []))

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
