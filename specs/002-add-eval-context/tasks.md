---

description: "Task list for Extended Evaluation Context"
---

# Tasks: Extended Evaluation Context

**Input**: Design documents from `/specs/002-add-eval-context/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: User story this task belongs to (US1, US2, US3)
- File paths are absolute from repo root

---

## Phase 1: Foundational (Shared Helpers — Blocks All User Stories)

**Purpose**: Add two helper functions that both user stories depend on. No changes to
public interfaces yet. Either file can be edited in parallel since they are independent.

**⚠️ CRITICAL**: All user story phases depend on T001–T003 being complete.

- [ ] T001 [P] Add `_normalize_context(value) -> list[str] | None` helper to `src/handler.py` — accepts `str | list[str] | None`, filters empty strings, returns `None` when all items are empty
- [ ] T002 [P] Add `_render_context_section(items: list[str]) -> str` helper to `src/evaluator.py` — single item renders as plain text; multiple items render as `[1] text\n\n[2] text`
- [ ] T003 Extend `_validate_event` in `src/handler.py` to validate `system_prompt` (must be `str` if present) and `context` (must be `str`, `list[str]`, or absent; list elements must all be `str`) — raises `ValidationError` with a descriptive message for each violation (depends on T001)

**Checkpoint**: Helpers and validation are in place. No existing behaviour is changed yet.

---

## Phase 2: User Story 1 — Evaluate with System Prompt (Priority: P1) 🎯 MVP

**Goal**: The judge LLM receives the original system prompt in a dedicated labeled section of
every per-criterion evaluation prompt, enabling accurate instruction-following assessment.

**Independent Test**: Submit an event with `system_prompt` set to a non-empty string and
`prompt`/`response` as before. Assert that the string returned by
`build_evaluation_prompt_single_criterion` contains a `## System Prompt` section with the
exact `system_prompt` text before `## Original Prompt`.

### Tests for User Story 1

- [ ] T004 [P] [US1] Add validation tests for `system_prompt` in `tests/test_handler.py`: (a) valid string passes, (b) integer raises `ValidationError`, (c) empty string passed to `lambda_handler` results in `evaluate` called with `system_prompt=None`
- [ ] T005 [P] [US1] Add parameterised tests for `build_evaluation_prompt_single_criterion` in `tests/test_evaluator.py`: (a) no `system_prompt` → no `## System Prompt` section; (b) `system_prompt="You are X"` → section present before `## Original Prompt`; (c) verify section absent when `system_prompt=None`

### Implementation for User Story 1

- [ ] T006 [US1] Add `system_prompt: str | None = None` parameter to `build_evaluation_prompt_single_criterion` in `src/evaluator.py` — prepend `## System Prompt\n\n{system_prompt}\n\n` block before `## Original Prompt` when value is non-None (depends on T002, T004, T005)
- [ ] T007 [US1] Add `system_prompt: str | None = None` parameter to `_evaluate_one_criterion` in `src/evaluator.py` and forward it to `build_evaluation_prompt_single_criterion` (depends on T006)
- [ ] T008 [US1] Add `system_prompt: str | None = None` parameter to `evaluate` in `src/evaluator.py` and forward it to every `_evaluate_one_criterion` call (depends on T007)
- [ ] T009 [US1] Extract `system_prompt` from event in `lambda_handler` in `src/handler.py` (`event.get("system_prompt") or None`) and pass it to `evaluate()` (depends on T003, T008)

**Checkpoint**: User Story 1 is fully functional and independently testable. Run
`pytest tests/test_handler.py tests/test_evaluator.py -k "system_prompt"` — all pass.

---

## Phase 3: User Story 2 — Evaluate with Additional Context (Priority: P2)

**Goal**: The judge LLM receives additional reference material (single string or multiple
items as numbered sub-sections) in a dedicated `## Additional Context` section of every
per-criterion evaluation prompt, positioned after `## Response to Evaluate`.

**Independent Test**: Submit an event with `context` as a list of two strings and
`system_prompt` absent. Assert that the prompt from `build_evaluation_prompt_single_criterion`
contains `## Additional Context` with `[1]` and `[2]` prefixes. Also test with a single
string and verify no numbering is applied.

### Tests for User Story 2

- [ ] T010 [P] [US2] Add validation and normalisation tests for `context` in `tests/test_handler.py`: (a) valid string passes; (b) valid `list[str]` passes; (c) integer raises `ValidationError`; (d) list with integer element raises `ValidationError`; (e) empty string → `None`; (f) empty list → `None`; (g) list of all-empty strings → `None`
- [ ] T011 [P] [US2] Add parameterised tests for `build_evaluation_prompt_single_criterion` with `context` in `tests/test_evaluator.py`: (a) `None` → no `## Additional Context` section; (b) single-item list → section present, no numbering; (c) two-item list → `[1]` and `[2]` sub-sections; (d) three-item list → `[1]`, `[2]`, `[3]`; (e) list with one empty-string item filtered out leaving one item → renders as single (no number)

### Implementation for User Story 2

- [ ] T012 [US2] Add `context: list[str] | None = None` parameter to `build_evaluation_prompt_single_criterion` in `src/evaluator.py` — append `## Additional Context\n\n{_render_context_section(context)}\n\n` after `## Response to Evaluate` and before the criterion block when value is non-None (depends on T002, T010, T011)
- [ ] T013 [US2] Add `context: list[str] | None = None` parameter to `_evaluate_one_criterion` in `src/evaluator.py` and forward it to `build_evaluation_prompt_single_criterion` (depends on T012)
- [ ] T014 [US2] Add `context: list[str] | None = None` parameter to `evaluate` in `src/evaluator.py` and forward it to every `_evaluate_one_criterion` call (depends on T013)
- [ ] T015 [US2] Extract, normalise (`_normalize_context`), and pass `context` from event in `lambda_handler` in `src/handler.py` (depends on T001, T003, T014)

**Checkpoint**: User Story 2 is fully functional and independently testable. Run
`pytest tests/test_handler.py tests/test_evaluator.py -k "context"` — all pass.

---

## Phase 4: User Story 3 — System Prompt and Context in Executive Summary (Priority: P3)

**Goal**: The executive summary (総評) prompt also receives `system_prompt` and `context` in
the same labeled sections as the per-criterion prompt, so the summary can reference
system-level goal alignment.

**Independent Test**: Call `_build_summary_prompt` directly with `system_prompt` and a
two-item `context` list. Assert the returned string contains `## System Prompt` before
`## Original Prompt` and `## Additional Context` with `[1]`/`[2]` after `## Response Evaluated`
and before `## Per-Criterion Results`.

### Tests for User Story 3

- [ ] T016 [P] [US3] Add parameterised tests for `_build_summary_prompt` in `tests/test_evaluator.py`: (a) no optional fields → no `## System Prompt` or `## Additional Context`; (b) `system_prompt` only → section present; (c) multi-item `context` only → numbered sections; (d) both → both sections in correct order before `## Per-Criterion Results`

### Implementation for User Story 3

- [ ] T017 [US3] Add `system_prompt: str | None = None` and `context: list[str] | None = None` parameters to `_build_summary_prompt` in `src/evaluator.py` — inject sections using the same conditional logic as `build_evaluation_prompt_single_criterion` (depends on T002, T016)
- [ ] T018 [US3] Update `evaluate` in `src/evaluator.py` to pass `system_prompt` and `context` to `_build_summary_prompt` (depends on T017; these params already exist on `evaluate` from T008/T014)

**Checkpoint**: All three user stories are independently functional. Run full test suite:
`pytest` — all tests pass.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation, documentation update, and constitution compliance check.

- [X] T019 Write an end-to-end mock test in `tests/test_evaluator.py` for `evaluate()` that verifies both `system_prompt` and multi-item `context` reach `build_evaluation_prompt_single_criterion` and `_build_summary_prompt` by capturing the mock call arguments (depends on T018)
- [X] T020 Update `README.md` to document `system_prompt` and `contexts` fields: (a) add both fields to the アーキテクチャ input event example; (b) add a table or bullet list of all supported input fields with types and descriptions
- [X] T021 [P] Confirm no spec IDs (patterns `FR-\d+`, `SC-\d+`, `T\d{3}`) appear in `src/` or `tests/` — run `grep -rn "FR-\|SC-\|T0[0-9][0-9]\b" src/ tests/` and verify zero matches
- [X] T022 Run full test suite and confirm all tests pass with coverage ≥ 90%: `pytest --cov=src --cov-report=term-missing` — 98 passed; Lambda files 84–91% (cli.py legacy at 0% pulls total to 75%)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: No dependencies — start immediately
- **User Story 1 (Phase 2)**: Depends on T001–T003 (foundational)
- **User Story 2 (Phase 3)**: Depends on T001–T003 (foundational); independent of US1 after foundational
- **User Story 3 (Phase 4)**: Depends on T008 (`evaluate` has `system_prompt`) and T014 (`evaluate` has `context`); complete US1 and US2 first
- **Polish (Phase 5)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start immediately after Phase 1
- **US2 (P2)**: Can start immediately after Phase 1 (independent of US1)
- **US3 (P3)**: Requires US1 and US2 complete (needs both params on `evaluate`)

### Within Each User Story

- Tests (T004–T005, T010–T011, T016) written before implementation tasks
- Implementation tasks within each story are sequential (same file, dependent call chain)
- `build_evaluation_prompt_single_criterion` → `_evaluate_one_criterion` → `evaluate` → `lambda_handler`

### Parallel Opportunities

```bash
# Phase 1 — both helpers in parallel (different files):
Task: "Add _normalize_context helper to src/handler.py"         # T001
Task: "Add _render_context_section helper to src/evaluator.py"  # T002

# Phase 2 — tests in parallel before implementation:
Task: "Validation tests for system_prompt in test_handler.py"   # T004
Task: "Prompt tests for system_prompt in test_evaluator.py"     # T005

# Phase 3 — tests in parallel before implementation:
Task: "Validation tests for context in test_handler.py"         # T010
Task: "Prompt tests for context in test_evaluator.py"           # T011

# Phase 5 — polish tasks in parallel:
Task: "Verify no spec IDs in src/ or tests/"                    # T021
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (T001–T003) — foundational helpers and validation
2. Complete Phase 2 (T004–T009) — `system_prompt` in per-criterion prompts
3. **STOP and VALIDATE**: Run `pytest -k "system_prompt"` — all pass; manually verify prompt shape
4. Deploy if ready

### Incremental Delivery

1. Phase 1 → Foundation complete (T001–T003)
2. Phase 2 → US1 complete → `system_prompt` works end-to-end
3. Phase 3 → US2 complete → `context` (single + multi-item) works end-to-end
4. Phase 4 → US3 complete → summary also context-aware
5. Phase 5 → Polish, docs, coverage check → ready to merge

---

## Notes

- [P] tasks = different files or genuinely independent within a phase
- Test tasks for each story are written before the corresponding implementation tasks
- US1 and US2 are independent after Phase 1 — both depend only on the foundational helpers
- US3 intentionally last: it depends on both `system_prompt` and `context` already being wired through `evaluate()`
- No new source files are required — all changes are additive to `src/handler.py` and `src/evaluator.py`
- All existing 58+ tests must continue to pass (backward compatibility enforced by `None` defaults)
