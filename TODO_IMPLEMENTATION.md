# TODO — Phase 0–3 Implementation

Source of truth: ACTION_PLAN_V2.txt ("MONOLITH — REMAINING WORK & FIX PLAN (V2)",
compiled 2026-10-31). This file is reference only — groups the Phase 0–3 changes
by phase and file so they can be tackled in order. No code changes are made
here.

Acceptance threads (from the plan): 20 half-session blocks, ONE per Saturday;
complete a block + apply regen twice → zero duplicates, count stable; no API
key material in /settings, /export, or any client response; refine loop forwards
the clarification; edit commitment → regen → no stale double-booked blocks;
morning gap before a class can be filled; tests run against a temp DB.

---

## Phase 0 — Secret + Safety Hygiene

### backend/app/routers/settings.py (Step 0.1 — fixes B3)
- [ ] GET /settings: never return ai_api_key plaintext
- [ ] Return "********" when key is set, "" when unset

### backend/app/db.py (Step 0.1 — fixes B3)
- [ ] GET /export (export_all): mask the key in the settings row the same way

### backend/app/main.py (Step 0.2 — fixes B3)
- [ ] CORS: drop allow_credentials=True OR pin explicit origins
  (["http://localhost:5174","http://127.0.0.1:5174"])

### Acceptance (Phase 0)
- [ ] curl /settings and /export contain no key material

---

## Phase 1 — Scheduler Correctness

### backend/app/scheduler.py
- [ ] Step 1.1 [B1]: advance cur_earliest to the NEXT working day when a task is
  non-splittable AND has a dependency (or always for non-splittable single-block
  tasks) — reuse the existing next-day expression unconditionally
- [ ] Step 1.4 [G1]: replace day_last_end pointer walk with per-day free-INTERVAL
  scan (subtract blocked intervals from the working window, iterate free
  segments) so pre-commitment morning gaps can be filled
- [ ] Step 1.5 [G4]: treat skipped like completed in engine busy/preserved
  filters + delete_future_flexible_blocks (ghosts gone, minutes refunded instead
  of rebooked)
- [ ] Step 1.7 [G6 partial]: clock hygiene — parse/compare ALL datetimes as
  naive-local; drop mixed UTC-aware "now" in reschedule-missed; wire
  settings.timezone via ZoneInfo(settings.timezone) helper

### backend/app/db.py
- [ ] Step 1.3 [G5]: update_commitment deletes future locked blocks of that
  commitment id

### backend/app/routers/schedule.py
- [ ] Step 1.2 [B2]: apply dedupe key set built from ALL preserved rows
  regardless of locked flag — add (start_dt, title) for completed/skipped/past
  rows too
- [ ] Step 1.6 [R2]: /schedule/blocks/{id}/move sets locked=True (mirror PATCH)
- [ ] Step 1.7 [G6 partial]: reschedule-missed compares against local now,
  not a UTC-aware "now" as strings

### backend/app/routers/tasks.py
- [ ] Step 1.5 [G4]: skip refunds remaining_minutes (+= block minutes)

### backend/app/routers/commitments.py
- [ ] Step 1.3 [G5]: update → after the db update, call the same
  delete-future-locked-blocks used by apply and trigger regen

### Acceptance (Phase 1)
- [ ] pytest suite green incl. new cadence + dedupe + gap tests

---

## Phase 2 — Courses / Generator / Commitments API

### backend/app/routers/projects.py (Step 2.1 — fixes G3)
- [ ] generate-sessions uses req.start_date as anchor
- [ ] Drop per-task deadline stamp; apply project deadline to LAST task (or none)
- [ ] estimated_weeks = math.ceil(block_count / sessions_per_week) with half flag
- [ ] Delete prior generated tasks + blocks for this project before regenerating
  (idempotent re-run)

### backend/app/routers/*.py (Step 2.2 — fixes R1)
- [ ] PATCH routers: switch `v is not None` filters to
  model_dump(exclude_unset=True) so explicit nulls clear deadline/target dates

### backend/app/routers/demo.py
- [ ] Step 2.3 [R3]: import_all wrapped in try/except → HTTP 400 with message;
  pre-validate FK ids / required keys before reset_db (never 500 after wipe)
- [ ] Step 2.4 [R4]: /demo/seed idempotent — skip seeds whose project name
  already exists

### backend/app/db.py (Step 2.5 — fixes R5)
- [ ] Migration shim: ensure-column helper (PRAGMA table_info +
  ALTER TABLE ADD COLUMN) called at startup
- [ ] apply preserves in-progress "today" blocks immutably for the remainder of
  the day (neither deleted nor double-booked)

---

## Phase 3 — Frontend Bug Fixes

### frontend/src/CommandBar.tsx
- [ ] Step 3.1 [G7a]: REFINE passes the composed string into submit() directly
- [ ] Step 3.2 [R6]: client-side normalize() for AI proposals (projects get name;
  tasks/commitments get title/start_time/end_time defaults via .get()); render
  proposal.summary ?? goal
- [ ] Step 3.3 [G8]: rename "Preview on Calendar" button to
  "REGENERATE PREVIEW (what-if)"; keep proposal cards as the plan preview

### frontend/src/TasksView.tsx (Step 3.4 — fixes G2)
- [ ] Wire api.tasks.update in an edit modal
- [ ] Add preferred_start / preferred_end inputs
- [ ] Add min/max session minutes inputs
- [ ] Forbid self-dependency in dependency dropdown
- [ ] Add OVERDUE (deadline < today) / WAITING (unsatisfied dependencies) badges

### frontend/src/CalendarView.tsx
- [ ] Step 3.5 [G9]: month fetch window from startOfMonth - 1 week
- [ ] Step 3.5 [G9]: move weekday header row out of grid-rows-6 flow
- [ ] Step 3.8 [P2]: hotkeys ignore when event target is BUTTON/checkbox

### frontend/src/components/Waybar.tsx (Step 3.6 — fixes G10)
- [ ] Compute day % from today's real blocks; reset at midnight
- [ ] Remove fake CPU/RAM readout or label it DECORATIVE

### frontend/src/api.ts
- [ ] Step 3.7 [P1]: add tiny guard(promise) helper that catches and surfaces a
  shared error banner state; wrap the ~12 try-less handlers
- [ ] Step 3.10 [R7]: BASE = "/api" (+ vite proxy rewrite)

### frontend/src/App.tsx
- [ ] Step 3.7 [P1]: shared error banner (surfaces guard errors)
- [ ] Step 3.7 [P1]: completedPercent initial value
- [ ] Step 3.8 [P2]: footer hint corrected ("[1-3] views" fix)

### frontend/src/CommitmentsView.tsx (Step 3.9 — fixes P4)
- [ ] Add `kind` select (fixed / one_time / weekly)
- [ ] Validate: weekly needs >= 1 day; one-time needs one_time_date
- [ ] Fix delete-confirm text for one-time entries

### frontend/vite.config.ts (Step 3.10 [R7] + P3)
- [ ] Proxy '/api' → target :8000 with rewrite stripping ^/api

### Cleanup (Step 3.10 [P3])
- [ ] npm uninstall react-big-calendar lucide-react react-router-dom
  @types/react-big-calendar
- [ ] Delete App.css, unused Material Symbols font link, scrollRef, dead api.ts
  methods, stale dist/, unused starter assets

---

Notes / out of scope for this file: Phase 4 (temp-DB fixture, strengthened
scenarios, regression tests, README) and Phase 5 (deferred) are deliberately not
listed. Files named here match the current repo layout (e.g. settings.py lives
at backend/app/routers/settings.py).
