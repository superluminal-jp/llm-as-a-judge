# Research: Extended Evaluation Context

**Feature**: 002-add-eval-context
**Date**: 2026-03-21

---

## Decision 1: Field names for new inputs

**Decision**: Use `system_prompt` and `context` as the new optional event fields.

**Rationale**: `system_prompt` is industry-standard terminology (used by Anthropic, OpenAI, and other LLM APIs). `context` is short, generic, and correctly conveys "additional reference material" without over-specifying the use case (RAG retrieved docs, conversation history, domain knowledge).

**Alternatives considered**:
- `system_message` — Too OpenAI-specific; the project supports multiple providers.
- `additional_context` — Verbose; `context` alone is unambiguous given the field's position alongside `prompt` and `response`.
- `documents` — Too narrow; excludes conversation history and other context types.

---

## Decision 2: Section ordering in judge prompts

**Decision**: System Prompt → Original Prompt → Response → Additional Context → Criterion.

**Rationale**: This order mirrors natural reading/evaluation flow: understand the task framing (system prompt) → read the question (prompt) → read the answer (response) → check against reference material (context) → apply the criterion. Placing context after the response follows the judge pattern of "evaluate what was produced, then cross-check against sources."

**Alternatives considered**:
- Context before Response — Unusual; judges typically read the response before consulting reference material.
- System Prompt embedded in Original Prompt section — Loses clarity; system-level instructions are semantically distinct from user-level prompts.

---

## Decision 3: context field type — string or list of strings

**Decision**: `context` accepts either a single string or a list of strings. Internally, a bare string is normalised to a list of one item. Multiple items are each rendered as a numbered sub-section (`[1]`, `[2]`, etc.) within the "Additional Context" block.

**Rationale**: RAG pipelines commonly retrieve multiple documents per query. Forcing callers to concatenate them into one string loses structural information and makes the prompt harder for the judge to read. A list representation maps directly to the retrieval result format and lets callers avoid manual serialisation. Accepting a bare string preserves simplicity for single-context use cases.

**Alternatives considered**:
- String only, caller concatenates — Loses structure; makes multi-document evaluation less reliable.
- List only — Creates a breaking API for simple single-context use cases; forces unnecessary list wrapping.
- Separate `context` (string) and `contexts` (list) fields — Two fields for the same concept causes confusion; union type is cleaner.

---

## Decision 4: Handling empty strings

**Rationale**: Empty string has no evaluation value and would add noise. Callers who pass `system_prompt: ""` most likely intend "no system prompt" rather than "the system prompt is an empty string." This matches the existing behavior for `criteria_file` (omit = use defaults).

**Alternatives considered**:
- Reject empty strings with ValidationError — Creates friction for callers doing programmatic construction.
- Render an empty section — Adds noise to every prompt; no evaluation benefit.

---

## Decision 5: Propagation strategy — parameter vs. wrapper object

**Decision**: Propagate `system_prompt` and `context` as explicit keyword parameters through the call chain (`handler.py` → `evaluate()` → `_evaluate_one_criterion()` / `_build_summary_prompt()`).

**Rationale**: The existing codebase uses explicit parameters throughout (no request-context object). Introducing a wrapper object for only two new optional fields would be over-engineering and inconsistent with the existing style. Python `Optional[str] = None` with `None` as the "absent" sentinel is the minimal, idiomatic approach.

**Alternatives considered**:
- `EvaluationContext` dataclass — Appropriate if the set of optional inputs was large or growing rapidly; premature for two fields.
- Thread-local / contextvars — Unnecessary complexity; the call chain is synchronous and straightforward.

---

## Decision 6: No changes to response schema

**Decision**: The Lambda response schema (`lambda-response.json`) is unchanged.

**Rationale**: The new fields are inputs to the judge, not outputs. The evaluation results (`criterion_scores`, `criterion_reasoning`, `reasoning`) already capture the judge's assessment; there is no need to echo back the system prompt or context in the response.

**Alternatives considered**:
- Echo `system_prompt` / `context` in response for traceability — Unnecessary for this feature; callers know what they sent.

---

## Decision 7: Backward compatibility

**Decision**: Both fields are optional with `None` as default. All existing code paths are exercised identically when the fields are absent.

**Rationale**: The spec explicitly requires full backward compatibility (FR-009). The simplest implementation is keyword arguments defaulting to `None`, with conditional section inclusion only when the value is a non-empty string.
