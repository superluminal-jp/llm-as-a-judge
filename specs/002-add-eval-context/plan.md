# Implementation Plan: Extended Evaluation Context

**Branch**: `002-add-eval-context` | **Date**: 2026-03-21
**Spec**: `specs/002-add-eval-context/spec.md`

---

## Summary

Add two optional input fields — `system_prompt` and `context` — to the Lambda evaluation event. When provided, these fields are injected into per-criterion judge prompts and the executive summary (総評) prompt as clearly labeled sections, enabling the judge LLM to evaluate responses relative to the instructions and reference material the original LLM received. No response schema changes. Full backward compatibility.

---

## Technical Context

| Item | Value |
|------|-------|
| **Language/Version** | Python 3.12 |
| **Lambda Runtime** | `python3.12` |
| **Primary Dependencies** | `anthropic`, `openai`, `boto3`, `aws-lambda-powertools` |
| **Testing** | `pytest` + `unittest.mock` (no real API calls) |
| **Target Platform** | AWS Lambda (`ap-northeast-1`) |
| **Performance Goals** | No change from 001 baseline (cold start <3s, p95 within Lambda timeout) |
| **Constraints** | Stateless; no new dependencies required; must not change response schema |
| **Scale/Scope** | 2 new optional input fields (`system_prompt`: string, `context`: string or list[string]); ~5 functions modified; ~20 new test cases |

---

## Constitution Check

*Constitution is a template with no project-specific principles defined yet. Applying general engineering quality gates.*

| Gate | Status | Notes |
|------|--------|-------|
| Minimal structure | ✅ | No new files in `src/`; changes confined to `handler.py` and `evaluator.py` |
| Testability | ✅ | All changes exercised by mock-based unit tests |
| Backward compatibility | ✅ | Both new fields default to `None`; no existing test modified |
| Stateless | ✅ | Fields are per-invocation; no state introduced |
| No new dependencies | ✅ | Pure parameter propagation; no library additions |

---

## Project Structure

### Documentation (this feature)

```text
specs/002-add-eval-context/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── contracts/
│   └── lambda-event.json  # Updated event schema (v2)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (changes only)

```text
src/
├── handler.py           # _validate_event: add system_prompt, context validation
│                        # _normalize_context: new helper (str|list → list[str]|None)
│                        # lambda_handler: extract and pass new fields to evaluate()
└── evaluator.py         # build_evaluation_prompt_single_criterion: add sections
                         # _render_context_section: new helper (list[str] → str)
                         # _build_summary_prompt: add sections
                         # _evaluate_one_criterion: propagate new params
                         # evaluate(): add system_prompt, context params

tests/
├── test_handler.py      # New: validate system_prompt, context fields
└── test_evaluator.py    # New: prompt construction with/without new fields
```

No changes to: `criteria.py`, `config.py`, `providers/`, CDK stack, response schema.

---

## Design Details

### 1. Validation (`src/handler.py`)

`_validate_event()` extended to validate the two new optional fields:

```python
# system_prompt: must be string if present
sp = event.get("system_prompt")
if sp is not None and not isinstance(sp, str):
    raise ValidationError("Event field 'system_prompt' must be a string when provided.")

# context: must be string or list[string] if present
ctx = event.get("context")
if ctx is not None:
    if isinstance(ctx, list):
        if not all(isinstance(item, str) for item in ctx):
            raise ValidationError(
                "Event field 'context' must be a list of strings; non-string elements found."
            )
    elif not isinstance(ctx, str):
        raise ValidationError(
            "Event field 'context' must be a string or list of strings when provided."
        )
```

A helper `_normalize_context` in `handler.py` normalises the raw input to `list[str] | None`:

```python
def _normalize_context(value) -> list[str] | None:
    """Normalise context to a list of non-empty strings, or None if absent."""
    if value is None:
        return None
    if isinstance(value, str):
        items = [value]
    else:
        items = value  # already validated as list[str]
    filtered = [s for s in items if s and s.strip()]
    return filtered if filtered else None
```

Lambda handler extracts and normalises:

```python
system_prompt: str | None = event.get("system_prompt") or None
context: list[str] | None = _normalize_context(event.get("context"))
```

Then passes them to `evaluate()`.

---

### 2. Prompt Construction (`src/evaluator.py`)

#### `build_evaluation_prompt_single_criterion`

New signature:
```python
def build_evaluation_prompt_single_criterion(
    prompt: str,
    response: str,
    criterion: "CriterionDefinition",
    system_prompt: str | None = None,
    context: list[str] | None = None,
) -> str:
```

Section injection (only when the value is non-None/non-empty):

```
[System Prompt section — if system_prompt]
## System Prompt

{system_prompt}

## Original Prompt

{prompt}

## Response to Evaluate

{response}

[Additional Context section — if context list is non-empty]
## Additional Context

{context[0]}           ← single item: no numbering

  — or, for multiple items —

[1] {context[0]}

[2] {context[1]}

## Criterion to Score
...
```

A helper function `_render_context_section(items: list[str]) -> str` builds the section body: single item renders without a number; multiple items render as `[1]`, `[2]`, etc.

#### `_build_summary_prompt`

New signature:
```python
def _build_summary_prompt(
    prompt: str,
    response: str,
    results: list[tuple[str, float, str]],
    system_prompt: str | None = None,
    context: list[str] | None = None,
) -> str:
```

Same conditional section injection using `_render_context_section`, with "## Additional Context" appearing after "## Response Evaluated" and before "## Per-Criterion Results".

#### `_evaluate_one_criterion`

New signature adds `system_prompt: str | None` and `context: list[str] | None`; passes them to `build_evaluation_prompt_single_criterion`.

#### `evaluate`

New signature:
```python
def evaluate(
    prompt: str,
    response: str,
    criteria: "EvaluationCriteria",
    provider: "BaseProvider",
    model: str,
    timeout: int,
    provider_name: str = "",
    system_prompt: str | None = None,        # new
    context: list[str] | None = None,        # new (already normalised by handler)
) -> dict:
```

Passes `system_prompt` and `context` to both `_evaluate_one_criterion` calls and `_build_summary_prompt`.

---

### 3. Contract Update

`specs/002-add-eval-context/contracts/lambda-event.json` adds `system_prompt` and `context` as optional string properties with `"additionalProperties": false` preserved.

The existing `specs/001-lambda-minimal-restructure/contracts/lambda-event.json` is **not modified** (it documents the 001 feature). Callers should reference the 002 contract going forward.

---

### 4. Test Strategy

**`test_handler.py`** — new test cases:
- `system_prompt` as a valid string → passes validation
- `context` as a valid string → passes validation
- `context` as a list of strings → passes validation
- `system_prompt` as integer → raises `ValidationError`
- `context` as integer → raises `ValidationError`
- `context` as list containing an integer → raises `ValidationError`
- `system_prompt` as empty string → normalised to `None`, evaluate called with `system_prompt=None`
- `context` as empty string → normalised to `None`
- `context` as empty list → normalised to `None`
- `context` as list with all-empty strings → normalised to `None`
- Both fields absent → existing behavior unchanged (no regression)

**`test_evaluator.py`** — new parameterised test cases:
- `build_evaluation_prompt_single_criterion` with no optional fields → no "System Prompt" or "Additional Context" sections
- With `system_prompt` only → "System Prompt" section present, "Additional Context" absent
- With `context` as single-item list → "Additional Context" section present, no numbering
- With `context` as multi-item list → numbered sub-sections `[1]`, `[2]`
- With both `system_prompt` and multi-item `context` → both sections present in correct order
- Same variants for `_build_summary_prompt`
- `evaluate()` end-to-end mock test: verify both new params reach the prompt builder

---

## Complexity Tracking

No Constitution violations. This change is minimal: two keyword arguments propagated through five functions, with two small helper functions added (`_normalize_context` and `_render_context_section`) and conditional sections added to two prompt builders.
