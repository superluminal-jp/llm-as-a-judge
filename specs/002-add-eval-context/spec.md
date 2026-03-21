# Feature Specification: Extended Evaluation Context

**Feature Branch**: `002-add-eval-context`
**Created**: 2026-03-21
**Status**: Draft
**Input**: 評価のインプットに "prompt", "response" だけでなく、システムプロンプトや追加コンテキストも追加できるように改善

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Evaluate with System Prompt (Priority: P1)

A developer has deployed an LLM with a specific system prompt (e.g., "You are a helpful customer service agent for Acme Corp. Always respond in polite Japanese."). They want the judge to evaluate the LLM's response with full awareness of those instructions, so that criteria like "instruction-following" and "tone" are scored relative to what the LLM was actually asked to do.

**Why this priority**: Without the system prompt, the judge cannot determine whether the response followed instructions correctly. This is the most common real-world evaluation gap and directly impacts evaluation accuracy.

**Independent Test**: Can be fully tested by submitting an evaluation request with `system_prompt` included, then verifying that the evaluation prompt presented to the judge LLM shows the system prompt in a dedicated section, and that criterion scores reflect system prompt adherence.

**Acceptance Scenarios**:

1. **Given** an evaluation request containing `prompt`, `response`, and `system_prompt`, **When** the evaluation runs, **Then** the judge LLM sees the system prompt in a clearly labeled section alongside the original prompt and response.
2. **Given** an evaluation request with only `prompt` and `response` (no `system_prompt`), **When** the evaluation runs, **Then** the system behaves identically to the current behavior (no regression).
3. **Given** a `system_prompt` value that is an empty string, **When** the request is submitted, **Then** it is treated as if no system prompt was provided (same as absent field).

---

### User Story 2 - Evaluate with Additional Context (Priority: P2)

A researcher is evaluating LLM responses in a RAG (Retrieval-Augmented Generation) pipeline. The model's response references multiple retrieved documents. The researcher wants to pass those documents as additional context so the judge can assess factual grounding and citation accuracy across all source material.

**Why this priority**: Additional context (retrieved documents, conversation history, domain-specific background) allows the judge to evaluate factual accuracy and relevance that would otherwise be impossible to assess without the source material.

**Independent Test**: Can be fully tested by submitting an evaluation request with `context` containing one or more reference documents, verifying the judge LLM's prompt includes all context items in clearly labeled sub-sections, and confirming that factual-accuracy criteria scores differ from evaluations without context.

**Acceptance Scenarios**:

1. **Given** an evaluation request containing `prompt`, `response`, and `context` as a single string, **When** the evaluation runs, **Then** the judge LLM sees the context in a clearly labeled section.
2. **Given** an evaluation request containing `context` as a list of strings (e.g., three retrieved documents), **When** the evaluation runs, **Then** the judge LLM sees each item in a numbered sub-section within the Additional Context section.
3. **Given** an evaluation request with both `system_prompt` and `context` (as a list), **When** the evaluation runs, **Then** the judge LLM sees both in clearly labeled, separate sections.
4. **Given** `context` as an empty string or an empty list, **When** the request is submitted, **Then** it is treated as if no context was provided.

---

### User Story 3 - System Prompt in Summary Generation (Priority: P3)

When generating the executive summary (総評), the judge has access to the system prompt and additional context in addition to per-criterion results. This ensures the summary can reference whether the overall response aligned with stated system-level goals.

**Why this priority**: The executive summary synthesises all dimensions. Without system prompt awareness, it may miss the most important evaluation dimension (instruction following). This is lower priority because per-criterion scores (P1/P2) already improve accuracy; the summary is additive.

**Independent Test**: Can be tested independently by verifying that the summary prompt includes the system prompt section when provided, separate from the per-criterion scores.

**Acceptance Scenarios**:

1. **Given** a completed per-criterion evaluation where `system_prompt` was provided, **When** the summary prompt is built, **Then** the system prompt appears in the summary prompt alongside the original prompt, response, and per-criterion results.

---

### Edge Cases

- What happens when `system_prompt` is provided as a non-string type (e.g., integer)? → Validation rejects with a clear error message.
- What happens when `context` is provided as a non-string, non-list type (e.g., integer or dict)? → Validation rejects with a clear error message.
- What happens when `context` is a list containing non-string elements (e.g., integers)? → Validation rejects with a clear error identifying which element is invalid.
- What happens when `context` is a list where some items are empty strings? → Empty string items are filtered out; remaining non-empty items are rendered.
- What happens when `context` is a list with all empty strings or an empty list? → Treated as if no context was provided.
- What happens when a single context item is extremely long (e.g., 100k+ tokens)? → The field is passed through as-is; token limits are the judge LLM provider's concern. No truncation is applied.
- What happens when neither `system_prompt` nor `context` is provided? → Fully backward-compatible; existing behavior is unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The evaluation input MUST accept an optional `system_prompt` field containing a string that represents the system-level instructions given to the evaluated LLM.
- **FR-002**: The evaluation input MUST accept an optional `context` field that provides additional reference material (e.g., retrieved documents, conversation history). The field accepts either a single string or a list of strings to support multiple independent context items.
- **FR-003**: When `system_prompt` is provided and non-empty, it MUST appear in a clearly labeled section of every per-criterion judge prompt, positioned before the original prompt.
- **FR-004**: When `context` is provided with one item, it MUST appear in a clearly labeled "Additional Context" section of every per-criterion judge prompt, positioned after the response and before the criterion block.
- **FR-005**: When `context` is provided with multiple items, each item MUST be rendered as a numbered sub-section within the "Additional Context" section (e.g., "[1]", "[2]").
- **FR-006**: When `system_prompt` is provided and non-empty, it MUST appear in the executive summary (総評) prompt.
- **FR-007**: When `context` is provided and non-empty, it MUST appear in the executive summary (総評) prompt using the same numbered rendering as per-criterion prompts.
- **FR-008**: Empty string values for `system_prompt` MUST be treated as absent.
- **FR-009**: An empty string, a list of all-empty strings, or an empty list for `context` MUST be treated as absent.
- **FR-010**: Non-string values for `system_prompt` MUST be rejected with a `ValidationError`.
- **FR-011**: Non-string, non-list values for `context` MUST be rejected with a `ValidationError`. A list containing non-string elements MUST also be rejected.
- **FR-012**: All existing behavior when neither field is provided MUST remain unchanged (full backward compatibility).

### Key Entities

- **EvaluationInput**: The data submitted per evaluation request. Currently holds `prompt` and `response`; extended to include optional `system_prompt` (string) and `context` (string or list of strings).
- **JudgePrompt**: The formatted string sent to the judge LLM for a single criterion. Structure is extended to include system prompt and context sections when present. Multiple context items are rendered as numbered sub-sections.
- **SummaryPrompt**: The formatted string sent to the judge LLM for executive summary generation. Extended similarly to JudgePrompt.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Evaluation requests including `system_prompt` produce judge prompts that contain the system prompt text within a dedicated, labeled section — verifiable in 100% of cases via unit tests.
- **SC-002**: Evaluation requests including `context` produce judge prompts that contain the context text within a dedicated, labeled section — verifiable in 100% of cases via unit tests.
- **SC-003**: Existing test suite (58 tests) continues to pass with no regressions — measured by test pass rate remaining at 100%.
- **SC-004**: Test coverage remains at or above 90% after implementing the new fields.
- **SC-005**: All combinations of the optional fields (neither, `system_prompt` only, `context` only, both) produce correct, well-formed judge prompts — verifiable through parameterised tests.
- **SC-006**: When `context` is a list of multiple items, each item appears as a numbered sub-section in the judge prompt — verifiable through unit tests covering lists of 1, 2, and 3+ items.

## Assumptions

- `system_prompt` is a flat string. Structured formats (e.g., list of role-tagged messages) are out of scope for this feature.
- Each `context` item is a flat string. Structured retrieval metadata (document titles, sources) is the caller's responsibility to format before submission.
- No changes to the response schema (`criterion_scores`, `criterion_reasoning`, `reasoning`, `judge_model`, `provider`) are required.
- The placement of sections in judge prompts follows the logical reading order: System Prompt → Original Prompt → Response → Context → Criterion.
- When `context` is a single string (not a list), it is treated internally as a list of one item for uniform processing.
