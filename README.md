# MONOLITH

An autonomous personal orchestration engine. Turning natural-language intent into structured plans, constraint-aware schedules, and adaptive execution timelines.

Built around deterministic scheduling, AI-driven reasoning, and local-first intelligence. Wrapped in an extreme brutalism theme.

## Stack

- **Backend:** Python 3.14 + FastAPI + SQLite
- **Frontend:** React + TypeScript + Vite + Tailwind

## Setup (Fedora/Linux)

### Backend

```bash
cd backend
uv venv .venv --python 3.14
uv pip install fastapi uvicorn pydantic pytest httpx
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173

## AI Configuration

Set provider/model/API key in Settings, or via environment variables before starting the backend:

- `GEMINI_API_KEY`, `GEMINI_MODEL`
- `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`

The app works without AI.

## Data

SQLite database: `backend/data/monolith.db`.

Backup by copying that file. Export JSON via `GET /export`.

## Tests

```bash
cd backend && .venv/bin/pytest -q
```

## Development phases

Remaining work is tracked in `action_plan.txt`, organized by phase:

- **Phase 0** — Secret + safety hygiene (API key masking, CORS).
- **Phase 1** — Scheduler correctness (dedupe, gap filling, skip refunds, clock hygiene).
- **Phase 2** — Courses / generator / commitments API (idempotent seed, import validation, migration shim).
- **Phase 3** — Frontend bug fixes (refine loop, error banner, TasksView inputs, preview rename).
- **Phase 4** — Reliability (this section): temp-DB test fixture, strengthened scenarios, regression tests.

Run the backend suite (30 tests, temp DB — never mutates `backend/data/monolith.db`):

```bash
cd backend && .venv/bin/pytest -q
```
