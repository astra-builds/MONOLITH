# MONOLITH AI Architecture Review and Implementation Roadmap

## Executive conclusion

The pasted review is directionally correct: MONOLITH currently has a strong deterministic scheduler and a provider abstraction, but the AI layer is primarily a one-shot extraction pipeline. The application has backend tools, yet the configured Gemini/OpenRouter providers are not given tool schemas and no model-driven tool loop exists. As a result, the system can propose new records, but it cannot reliably inspect, identify, modify, verify, and reschedule existing records.

That is the main reason simple “create a course” requests work while requests such as “rename Monday courses,” “change this to university,” or “continue this routine until 3 February” fail.

The target architecture should be:

```text
user message
  -> intent/router
  -> state-aware operator loop
       -> read focused state
       -> build a typed change set
       -> deterministic preview/validation
       -> clarification or confirmation
       -> one atomic application
       -> re-read and report actual result
  -> calendar refresh
```

The model should decide what the user means and which controlled operation is needed. The backend must resolve records, enforce invariants, run the scheduler, own transactions, and report facts. The model must never invent calendar timestamps or directly mutate SQLite.

## Findings and corrections to the pasted review

### Findings I agree with

1. **There is no real provider tool calling.** `GeminiProvider` and `OpenRouterProvider` only send a text prompt through `extract()`. Their `capabilities()` claim tool calling, but the payloads contain neither provider-native function declarations nor OpenAI-compatible `tools` definitions.

2. **The conversation path is brittle.** `handle_conversation_message()` uses keyword branches and sends every other request to `plan_request()`. A follow-up therefore has no reliable update/inspect route and can create duplicate records.

3. **The context is too broad and stale.** `get_planning_context()` loads all projects, tasks, commitments, blocks, availability rules, and conversation messages into one prompt. This will become expensive and less reliable as the calendar grows. Focused read tools are a better source of truth.

4. **Refine loses proposal continuity.** `CommandBar.refine()` concatenates text and submits a new plan. It does not update the existing proposal or preserve a structured clarification state.

5. **The system lacks a genuine inspect → act → observe loop.** There is no bounded state machine that can inspect Monday records, choose matching IDs, modify them, preview the schedule, observe conflicts, and correct or ask a question.

### Corrections and additional issues

1. **“Tool registry exists” is not the same as “tool calling exists.”** The registry currently exposes descriptions and a manual `/ai/tools/execute` endpoint, but not JSON Schema argument definitions suitable for Gemini or OpenRouter. It is an application API, not yet a model-facing function interface.

2. **The registry has a false conflict tool.** `inspect_scheduling_conflicts` currently returns an empty list and a message saying to use proposal preview. It must perform an actual conflict/unscheduled analysis or be removed from model-visible tools.

3. **The existing write tools are not a safe multi-operation transaction.** `execute_tool()` runs each write independently. A model can update three Monday records, fail on the fourth, and leave a partial change. Idempotency prevents some replays, but it does not provide all-or-nothing behavior.

4. **Direct writes do not consistently regenerate the schedule.** `update_commitment()` deletes future locked blocks, but the tool does not itself regenerate the affected horizon. A follow-up can therefore leave the calendar temporarily incomplete or stale unless another endpoint is called.

5. **Matching is underspecified.** “Courses on Mondays” requires a backend query/filter that returns stable IDs, weekday membership, entity type, and confidence/ambiguity information. The model should not infer identity from a giant title dump or be allowed to update every approximate match silently.

6. **The data model issue is more nuanced than “add task fields.”** `commitments` already have `tag` and `end_date`; `projects` already have `kind`. Tasks do not have a tag/category or an active-through date. More importantly, the product needs explicit semantics:

   - A class or fixed appointment is a recurring `commitment`.
   - A course/project is a `project` containing work tasks.
   - A deadline is a milestone or task/project deadline.
   - “Study this every Monday until 3 February” is either a recurring study commitment or a recurring task policy, not merely a task deadline.

   Adding columns without defining those semantics will create more ambiguity.

7. **The current proposal model is create-oriented.** Preview inputs append proposed tasks and commitments. It has no first-class update/delete/change-set operations, target IDs, preconditions, or affected-record list. That must be extended before an operator can safely edit existing plans.

8. **The current approval boundary is incomplete.** The UI approves a generated schedule, but tool-level confirmation and proposal approval are separate concepts. A single request should produce one reviewable change set, with risk and affected records, then apply atomically.

9. **Provider capability reporting is optimistic.** Both adapters report structured output, tool calling, and streaming as true, but only plain request/response extraction is implemented. Capabilities should be negotiated/configured per provider/model and tested with a real request shape.

10. **Dates need an explicit clock policy.** Relative dates such as “until 3 February,” “next Monday,” and “on the 7th” need the application timezone, current local date, year rollover rules, and inclusive/exclusive end-date semantics supplied by the backend—not left implicit in a prompt.

11. **Autonomy needs stronger limits.** “Full autonomy” should not mean unrestricted model writes. It should still enforce allowed operation types, affected-record limits, date horizon, no deletion without explicit approval, and a transaction-level audit record.

## Target capabilities

The first complete milestone should support these cases end to end:

1. “I have three classes Monday from 09:00 to 12:00 and Agentic AI at 17:00.”
   - Extract three fixed events or one clearly represented multi-event request.
   - Preserve Monday, times, timezone, and recurrence.
   - Preview the resulting commitment blocks.

2. “Rename the courses on Mondays.”
   - Query Monday commitments/tasks.
   - If one exact target exists, propose the rename.
   - If several targets exist and “courses” is ambiguous, ask which records or show a selectable list.
   - Apply all confirmed edits atomically and regenerate affected future blocks.

3. “Change the section to university because it is a university course.”
   - Resolve “it” from conversation/proposal state.
   - Update the appropriate project/task/commitment category using explicit taxonomy.
   - Show the exact record and old/new values before applying.

4. “Follow this routine until 3 February, then stop; my capstone deadline is 7 February.”
   - Create/update a bounded recurrence with an inclusive `end_date`.
   - Represent the capstone as a milestone/deadline with its own date.
   - Regenerate only the affected future horizon.
   - Verify that no recurrence blocks exist after 3 February and that the deadline remains on 7 February.

## Phase-by-phase action plan

### Phase 0 — Freeze behavior, terminology, and evaluation fixtures

**Goal:** establish a reliable baseline before changing the operator.

Tasks:

- Define the domain vocabulary: project, task, course, class/commitment, routine, milestone, deadline, category/tag, and end date.
- Decide inclusive end-date semantics: a recurrence with `end_date = 2027-02-03` may generate a block on 3 February but never after it.
- Add a fixed application clock/timezone helper for tests and prompt metadata.
- Create seeded fixtures for Monday classes, a recurring course routine, a capstone milestone, duplicate titles, and ambiguous references.
- Add golden end-to-end tests for the four target capabilities above using a fake provider that emits tool calls, not canned final database results.
- Record the current backend test baseline and make the test command deterministic. Investigate why the observed full suite did not finish promptly.

Acceptance:

- Fixtures can reproduce each failure without an external API.
- Tests assert database rows, schedule blocks, dates, IDs, and absence of duplicates.

### Phase 1 — Make provider contracts truthful and tool schemas real

**Goal:** give models a typed, provider-neutral operator interface.

Tasks:

- Extend `AIProvider` with a common chat-turn contract: messages, tool definitions, tool calls, text, finish reason, usage, and provider request ID.
- Define JSON Schema for every model-visible tool argument. Do not expose only descriptions.
- Add provider adapters:
  - Gemini `function_declarations` and function-call response parsing.
  - OpenRouter/OpenAI-compatible `tools` and `tool_calls` parsing.
- Normalize provider errors, malformed calls, unknown tools, invalid arguments, rate limits, and context limits.
- Make `capabilities()` reflect implementation/model configuration rather than optimistic constants.
- Keep `extract()` as a compatibility/offline path, but route new operator requests through the common tool-capable contract.

Acceptance:

- Adapter tests parse representative Gemini and OpenRouter request/response fixtures.
- Unsupported models fall back clearly to structured extraction or offline mode.
- No provider API key is exposed to the frontend or prompt context.

### Phase 2 — Build a bounded, state-aware operator loop

**Goal:** replace one-shot extraction for conversational operations.

Tasks:

- Add an `AI run`/operation state machine with states such as `classify`, `inspect`, `draft_change_set`, `preview`, `await_confirmation`, `apply`, `verify`, `complete`, and `failed`.
- Pass only a compact system prompt, user/conversation turns, relevant proposal state, and tool results—not the entire database snapshot every turn.
- Enforce limits: maximum tool turns, maximum records returned, maximum mutations, time budget, and token budget.
- Require read-before-write for updates/deletes and include target IDs plus a short reason in every mutation.
- Return a typed final result: answer, clarifications, proposed changes, preview diff, warnings, and actual applied result.
- Store run metadata and each tool call/result in `ai_operations` (or a dedicated `ai_runs` table) with correlation IDs.

Acceptance:

- A fake model can call `get_commitments`, inspect its result, call `update_commitment`, call preview, and stop.
- The loop cannot call a write tool before a target has been resolved.
- Infinite loops and repeated identical tool calls terminate safely.

### Phase 3 — Replace broad context with focused, semantic query tools

**Goal:** make identification accurate and prompts efficient.

Tasks:

- Upgrade read tools with validated filters: date range, weekday, title search, project/category, recurrence, status, and entity type.
- Add a semantic search/resolve tool that returns candidate records, exact match status, and ambiguity—not a guessed ID.
- Implement `inspect_scheduling_conflicts` using the real scheduler and current state; never return a hardcoded empty result.
- Add a focused `get_conversation_state`/`get_pending_proposal` tool for pronouns and follow-ups.
- Bound calendar reads by date range and return compact records with IDs and relevant fields.
- Add indexes/query paths once fixture data shows a need; avoid premature broad caching.

Acceptance:

- “Monday courses” returns only relevant candidates with stable IDs.
- Large calendars do not require serializing every historical block into every prompt.
- Ambiguous matches produce a clarification rather than a bulk mutation.

### Phase 4 — Introduce a first-class change-set/proposal model

**Goal:** make create, update, delete, and schedule changes reviewable together.

Tasks:

- Extend proposal intent with typed operations, for example:
  - `create_record`
  - `update_record` with `entity_type`, `target_id`, `expected_version`, and field diff
  - `delete_record` requiring explicit approval
  - `set_recurrence_policy`
  - `schedule_request`
- Store target snapshots or updated-at versions so stale proposals are rejected instead of overwriting newer user edits.
- Build a backend change-set validator that checks references, date ordering, recurrence rules, duplicate risk, authorization/autonomy, and operation limits.
- Generate one schedule preview/diff from the proposed domain changes.
- Keep the current atomic proposal approval path, but extend its transaction to apply updates as well as creates.

Acceptance:

- A proposal clearly shows “Monday 09:00 Biology → University Biology” and affected future blocks.
- Applying a multi-record change either applies all valid operations or none.
- Re-approval and stale-version approval are safely rejected.

### Phase 5 — Clarification continuity and conversation UX

**Goal:** make the assistant feel coherent and comfortable.

Tasks:

- Replace keyword routing in `handle_conversation_message()` with the operator loop; retain deterministic fast paths only for unambiguous complete/skip actions.
- Turn clarifications into a persistent pending run/proposal. A reply should continue that run instead of concatenating a new prompt.
- Keep user-visible messages separate from machine state; store structured turns and tool events, not only a JSON blob of mixed values.
- Show candidate records when ambiguity exists and let the user select them.
- Display old value → new value, affected dates, moved/created/removed blocks, warnings, and “why” scheduler reasons.
- Remove placeholder UI telemetry such as hardcoded prompt token/latency/hash values; show real values or omit them.

Acceptance:

- The user can answer a clarification and complete the original operation without re-entering context.
- The UI makes confirmation scope obvious and never implies a change was applied before it was.

### Phase 6 — Domain model improvements for routines, categories, and deadlines

**Goal:** represent the user’s language without overloading unrelated fields.

Tasks:

- Add task category/tag only if product taxonomy confirms tasks need it; otherwise use project/category relations consistently.
- Add a task active-through/end date only for recurring task policies. Do not reinterpret ordinary completion deadlines.
- Consider a first-class routine/recurrence policy entity if recurring study work must generate task instances, track completion, and stop independently of a fixed commitment.
- Add milestone APIs/UI for capstone deadlines and project phases.
- Define whether a course is a project, a recurring commitment, or both, and enforce the relationship in validation.
- Add migration shims and export/import coverage for every new field/entity.

Acceptance:

- The capstone deadline is distinct from the routine’s final occurrence.
- The scheduler receives normalized records and remains deterministic; the model does not write block timestamps.

### Phase 7 — Schedule correctness, performance, and safe regeneration

**Goal:** make complex changes reliable at realistic scale.

Tasks:

- Make affected-horizon regeneration an explicit service operation invoked by change-set application.
- Preserve completed, skipped, locked, past, and manually moved blocks according to documented policy.
- Add recurrence boundary tests, timezone/DST tests, deadline-at-midnight tests, and stale-preview tests.
- Optimize slot search by precomputing/merging daily free intervals and avoiding repeated full conflict scans where profiling proves it matters.
- Add indexes for common date/entity queries and measure prompt size, tool latency, schedule latency, and DB transaction time.

Acceptance:

- Changing a commitment updates only the intended future horizon and leaves historical truth intact.
- Benchmarks cover at least 1,000 schedule blocks and a multi-month horizon.

### Phase 8 — Autonomy rollout and production hardening

**Goal:** ship progressively without risking user data.

Tasks:

- Keep `suggestion` as preview-only, `assisted` as the default, and define exact safe-write classes for any automatic action.
- Require explicit confirmation for deletion, bulk edits, deadline changes, and changes above a configurable record/date threshold.
- Add dry-run mode, undo/revert for the last applied change set, and export/backup before destructive operations.
- Add provider contract tests, fault injection, retry policy, audit-log inspection, and privacy checks.
- Add evaluation cases for ambiguity, pronouns, duplicate requests, malformed tool calls, provider outage, partial failure, and adversarial instructions in record text.
- Roll out behind a feature flag: read-only operator, preview-only mutations, assisted apply, then narrowly scoped autonomy.

Acceptance:

- Every applied mutation has an auditable change-set ID and actual result.
- A provider failure or interrupted run cannot silently leave an unexplained partial plan.
- The application remains fully usable manually and with offline parsing.

## Recommended implementation order

Do not start by adding only `tasks.tag` and `tasks.end_date`, and do not let the model directly call independent database writes. The highest-leverage sequence is:

1. Phase 0 evaluation fixtures.
2. Phase 1 real provider tool contracts.
3. Phase 2 bounded operator loop.
4. Phase 3 focused entity resolution and real conflict inspection.
5. Phase 4 atomic change sets and proposal diffs.
6. Phase 5 clarification/UI continuity.
7. Phase 6 domain additions.
8. Phase 7 performance and schedule hardening.
9. Phase 8 guarded autonomy rollout.

This order lets the existing scheduler remain the execution authority while the AI layer becomes a reliable state-aware operator around it.

## Definition of done for the first major release

- The four target scenarios pass as automated end-to-end tests.
- Existing records are resolved by ID with ambiguity handling.
- Updates, creates, and bounded recurrence changes appear in one previewable atomic change set.
- The schedule is regenerated and verified after apply.
- Clarifications continue the same run.
- Provider capabilities and failures are truthful.
- No model-generated timestamp bypasses the scheduler.
- The user can see what changed, why it changed, and undo/revert the last change set.
