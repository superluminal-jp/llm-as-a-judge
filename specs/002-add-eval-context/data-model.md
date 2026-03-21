# Data Model: Extended Evaluation Context

**Feature**: 002-add-eval-context
**Date**: 2026-03-21

---

## Entities

### EvaluationInput (Lambda Event)

Represents the data submitted to the Lambda function per evaluation request.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | `string` | Yes | The question or instruction given to the evaluated LLM. Must be non-empty. |
| `response` | `string` | Yes | The LLM response to evaluate. Must be non-empty. |
| `system_prompt` | `string` | No | System-level instructions given to the evaluated LLM before the conversation. Empty string treated as absent. |
| `context` | `string \| list[string]` | No | Additional reference material (e.g., retrieved documents, conversation history). Accepts a single string or a list of strings for multiple items. Empty string, empty list, or a list of all-empty strings treated as absent. |
| `provider` | `string` | No | LLM provider to use as judge (`anthropic`, `openai`, `bedrock`). Defaults to env var. |
| `judge_model` | `string` | No | Specific judge model name. Defaults to provider-specific env var. |
| `criteria_file` | `string` | No | S3 URI (`s3://...`) pointing to a JSON criteria file. Defaults to built-in balanced criteria. |

**Validation rules**:
- `prompt` and `response`: required, non-empty string
- `system_prompt`: optional; if present, must be a string (non-string → `ValidationError`); empty string treated as absent
- `context`: optional; if present, must be a string or a list of strings (other types → `ValidationError`); a list with non-string elements → `ValidationError`; empty string, empty list, or all-empty-string list treated as absent
- `provider`: if present, must be one of `["anthropic", "openai", "bedrock"]`
- `criteria_file`: if present, must start with `s3://`

---

### JudgePrompt (per-criterion)

The formatted string sent to the judge LLM for a single criterion. Structure varies by presence of optional fields.

**Section order** (only sections with content are rendered):

```
[1] ## System Prompt         ← rendered only when system_prompt is non-empty
    {system_prompt}

[2] ## Original Prompt       ← always rendered
    {prompt}

[3] ## Response to Evaluate  ← always rendered
    {response}

[4] ## Additional Context    ← rendered only when context list has non-empty items
    [1] {context_items[0]}
    [2] {context_items[1]}   ← numbered sub-sections when multiple items
    ...

[5] ## Criterion to Score    ← always rendered
    ...criterion block...
```

Single-item context is rendered without a number (same as multi-item with index 1, but the number is omitted when there is only one item for cleaner output).

---

### SummaryPrompt (executive summary / 総評)

The formatted string sent to the judge LLM to synthesise all per-criterion results.

**Section order** (same conditional logic and numbered rendering as JudgePrompt):

```
[1] ## System Prompt         ← rendered only when system_prompt is non-empty
    {system_prompt}

[2] ## Original Prompt       ← always rendered
    {prompt}

[3] ## Response Evaluated    ← always rendered
    {response}

[4] ## Additional Context    ← rendered only when context list has non-empty items
    [1] {context_items[0]}
    [2] {context_items[1]}   ← same numbered rendering as JudgePrompt

[5] ## Per-Criterion Results ← always rendered
    ...criterion blocks...

[6] ## Instructions          ← always rendered
    ...synthesis instructions...
```

---

### EvaluationResult (Lambda Response)

**Unchanged** from the 001 contract. The response schema does not include `system_prompt` or `context`.

| Field | Type | Description |
|-------|------|-------------|
| `criterion_scores` | `object` | Per-criterion scores (1–5), keyed by criterion name |
| `criterion_reasoning` | `object` | Per-criterion reasoning text, keyed by criterion name |
| `reasoning` | `string` | Executive summary (総評) in Japanese |
| `judge_model` | `string` | Model name used as judge |
| `provider` | `string` | Provider identifier |

---

## State Transitions

No state transitions — the Lambda function is stateless. All data is consumed within a single invocation.

---

## Internal Parameter Flow

```
lambda_handler(event)
    │
    ├─ _validate_event(event)
    │     validates: system_prompt (optional str), context (optional str | list[str])
    │
    └─ evaluate(
           prompt=event["prompt"],
           response=event["response"],
           system_prompt=event.get("system_prompt") or None,   ← new
           context=_normalize_context(event.get("context")),    ← new (normalises str/list → list[str] | None)
           criteria=...,
           provider=...,
           model=...,
           timeout=...,
           provider_name=...,
       )
           │
           ├─ _evaluate_one_criterion(
           │      criterion, prompt, response,
           │      system_prompt, context,                       ← new
           │      provider, model, timeout, provider_label
           │  )
           │      └─ build_evaluation_prompt_single_criterion(
           │             prompt, response, criterion,
           │             system_prompt, context                 ← new
           │         )
           │
           └─ _build_summary_prompt(
                  prompt, response, results,
                  system_prompt, context                        ← new
              )
```
