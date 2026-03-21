<!--
SYNC IMPACT REPORT
==================
Version change: (unversioned template) → 1.0.0
Ratification: 2026-03-21 (initial adoption)
Last amended: 2026-03-21

Principles added (all new — first constitution):
  I.   Living Documentation
  II.  Production-Grade Observability
  III. Codebase Clarity
  IV.  Minimal Structure
  V.   Test Coverage

Templates reviewed:
  ✅ .specify/templates/plan-template.md
       — "Constitution Check" gates are derived at runtime from this file; no structural change needed.
  ✅ .specify/templates/spec-template.md
       — No spec-number formats introduced; FR-NNN and SC-NNN labels are spec-internal only (not propagated to code). No change needed.
  ✅ .specify/templates/tasks-template.md
       — Logging task (T017) and documentation task (TXXX) already present as examples; aligns with Principles I and II.
  ✅ README.md
       — No structural change needed; Principle I governs its ongoing maintenance.

Follow-up TODOs:
  - None. All principles are fully specified.
-->

# LLM-as-a-Judge Constitution

## Core Principles

### I. Living Documentation

README.md and all documentation in `docs/` MUST accurately reflect the current state of the
codebase at all times. A code change and its corresponding documentation update MUST land in
the same commit — documentation-only follow-up commits are a violation.

- Every public-facing interface, input schema, and output schema MUST be documented before
  a feature is considered complete.
- Code examples in documentation MUST be tested or explicitly marked as illustrative.
- Architecture diagrams and data-flow descriptions MUST be updated when the architecture changes.
- Rationale: Stale documentation is worse than no documentation; it actively misleads contributors
  and users.

### II. Production-Grade Observability

Logging, error handling, and in-code comments MUST follow professional production standards
from day one — not as a polish step.

**Logging**:
- All log entries MUST use structured JSON logging (AWS Lambda Powertools `Logger`).
- Log levels MUST be used precisely: `DEBUG` for diagnostic detail, `INFO` for lifecycle events,
  `WARNING` for recoverable anomalies, `ERROR`/`CRITICAL` for unrecoverable failures.
- Every LLM API call MUST log its duration when above the defined threshold.

**Error handling**:
- Exceptions MUST propagate via `raise`, never via `return {"error": ...}`.
- All caught exceptions MUST be logged with `exc_info=True` before re-raising.
- Error cause chains MUST be preserved: `raise NewError("...") from original`.
- Every module MUST define or reference the project exception hierarchy (`LlmJudgeError` and
  its subclasses).

**Comments**:
- Comments MUST explain *why*, not *what*. Redundant comments (e.g., `# increment counter`)
  are prohibited.
- Cold-start optimisation points MUST be marked with `# Cold-start: <reason>`.
- Every non-trivial function MUST have a Google-style docstring (Args / Returns / Raises).
- Module-level docstrings MUST describe responsibilities, key classes/functions, and caveats.

### III. Codebase Clarity

Source code MUST be free of specification artefact language. Spec IDs, requirement numbers,
and spec-workflow terminology MUST NOT appear in production code or tests.

- Identifiers such as `FR-001`, `SC-002`, `US3`, `T014`, or any `speckit`-specific label
  MUST NOT appear in `src/` or `tests/`.
- Code uses domain vocabulary: `prompt`, `response`, `criterion`, `provider`, `evaluation`.
- Comments that reference design decisions MUST do so in plain English, not by citing a
  spec artefact ID. Point to the decision in `research.md` only in `specs/` documents,
  never in production code.
- Rationale: The codebase must remain readable and maintainable independently of the
  specification artefacts that motivated its creation.

### IV. Minimal Structure

The simplest design that satisfies requirements MUST be chosen. Complexity requires explicit
justification documented in the plan's Complexity Tracking table.

- AWS Lambda flat structure: source modules at `src/` with no unnecessary sub-packaging.
- No new module is introduced unless it has a single, clearly stated responsibility.
- The function MUST remain stateless: no file-system persistence, no module-level mutable
  state beyond cold-start caches.
- Abstractions (base classes, protocols, helpers) MUST be justified by at least two concrete
  use cases at the time of introduction.
- YAGNI (You Aren't Gonna Need It) applies: features and generalisations not required by
  the current specification MUST NOT be implemented.

### V. Test Coverage

All production code MUST be covered by automated tests using mocks — no real API calls in
the test suite.

- Test coverage MUST remain at or above 90% after every change.
- New code paths introduced by a feature MUST have corresponding unit tests before the
  feature branch is merged.
- Parameterised tests are preferred over duplicated test cases.
- Tests MUST verify behaviour, not implementation: assert on outputs and side-effects,
  not on internal call sequences unless the sequence is the contract.

## Quality Standards

The following minimum bars apply to every change merged to `main`:

| Dimension | Requirement |
|-----------|-------------|
| Documentation | README and relevant docs updated in same commit |
| Test coverage | ≥ 90% (`pytest --cov`) |
| Logging | Structured JSON; no bare `print()` in production code |
| Error handling | All exceptions raised, not returned; cause chains preserved |
| Code clarity | No spec IDs in `src/` or `tests/`; comments explain why |
| Complexity | Any new abstraction or module justified in plan's Complexity Tracking |

## Development Workflow

1. **Specify** → **Plan** → **Tasks** → **Implement** (spec-kit workflow).
2. Feature branches branch from `main` following the naming convention in `.claude/rules/`.
3. Documentation and code changes MUST be committed together (Principle I).
4. The Constitution Check section in every `plan.md` MUST list each principle and its
   gate status before implementation begins.
5. Any principle violation in a plan MUST be entered in the Complexity Tracking table
   with a justification. Unjustified violations block implementation.

## Governance

This constitution supersedes all other practices and defaults for this project. Where a
global rule (e.g., from `~/.claude/rules/`) conflicts with a project-specific principle
here, the more restrictive rule applies.

**Amendment procedure**:
- PATCH (typos, clarifications, non-semantic wording): single-author edit, no review required.
- MINOR (new principle or materially expanded guidance): document rationale in commit message.
- MAJOR (principle removal or redefinition with backward-incompatible governance change):
  explicit user approval required; migration plan documented.

**Version semantics**: Follows semantic versioning. Bump is determined by the nature of
the change per the amendment procedure above.

**Compliance review**: Every `plan.md` Constitution Check and every PR review MUST verify
compliance with all five principles. Complexity must be justified. Use `specs/` for
design artefacts; use `src/` for clean, spec-free code.

**Version**: 1.0.0 | **Ratified**: 2026-03-21 | **Last Amended**: 2026-03-21
