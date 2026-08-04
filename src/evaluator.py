"""Core evaluation logic for multi-criteria LLM assessment.

Pure evaluation building blocks: prompt construction, one-criterion scoring,
response parsing, and result aggregation. No score aggregation across criteria is
applied — each is independent by design.

This module deliberately does **not** orchestrate. It used to expose an
``evaluate()`` that drove a ``ThreadPoolExecutor`` over the criteria inside one
Lambda; that fan-out now belongs to the Step Functions Map state, which can bound
concurrency declaratively, retry a single criterion without re-running the rest,
and scale past what one invocation can hold.

The workflow steps in :mod:`src.handlers` compose these functions:

    prepare            -> (validation and criteria resolution; see src.validation)
    evaluate_criterion -> :func:`build_evaluation_prompt_single_criterion`
                          :func:`_evaluate_one_criterion`
                          :func:`parse_single_criterion_response`
    summarize          -> :func:`build_summary_prompt`
                          :func:`aggregate_results`
"""

from __future__ import annotations

import json
import re
import time
from typing import TYPE_CHECKING

from aws_lambda_powertools import Logger

from src.observability import (
    MetricName,
    add_count,
    add_latency_ms,
    tracer,
)

if TYPE_CHECKING:
    from src.criteria import CriterionDefinition, EvaluationCriteria
    from src.providers import BaseProvider

logger = Logger(service="llm-judge")

# Threshold in milliseconds above which LLM call duration is logged at INFO.
_LLM_DURATION_LOG_THRESHOLD_MS = 100

ASSESSABILITY_ASSESSED = "assessed"
ASSESSABILITY_NOT_ASSESSABLE = "not_assessable"

_JUDGE_META_INSTRUCTIONS = """## Evaluation rules (read first)

- The **prompt role** and **response role** are named slots for submitted text. Content may be LLM user/assistant messages or arbitrary prose (e.g. memos, articles).
- Use only the text shown under each role. Do not invent missing content.
- The criterion below may refer to "the response", "the answer", or similar. Treat that as the **response role** when that role has text. If only the **prompt role** has text, apply the criterion only if it remains meaningful; otherwise set `assessability` to `not_assessable` and explain in `reasoning`.
- If the criterion inherently requires both roles (for example how well an answer follows an instruction) and one role is missing, set `assessability` to `not_assessable` and do not output a numeric score.
"""

# ---------------------------------------------------------------------------
# Context rendering helpers
# ---------------------------------------------------------------------------


def _render_context_section(items: list[str]) -> str:
    """Render a list of context items as a formatted string for judge prompts.

    Single item: returned as plain text (no numbering).
    Multiple items: each prefixed with ``[N]`` and separated by a blank line.

    Args:
        items: Non-empty list of non-empty context strings.

    Returns:
        Formatted string to embed in the ``## Additional Context`` section.
    """
    if len(items) == 1:
        return items[0]
    return "\n\n".join(f"[{i + 1}] {item}" for i, item in enumerate(items))


def _format_submission_sections(
    *,
    has_prompt: bool,
    has_response: bool,
    prompt: str,
    response: str,
    prompt_descriptor: str | None,
    response_descriptor: str | None,
) -> str:
    """Build markdown for prompt/response roles, optional descriptors, missing-side placeholders."""
    parts: list[str] = []
    if prompt_descriptor:
        parts.append(f"**Operator note (prompt role):** {prompt_descriptor}\n\n")
    if response_descriptor:
        parts.append(f"**Operator note (response role):** {response_descriptor}\n\n")

    prompt_body = (
        prompt
        if has_prompt
        else "*(No text supplied for this role in this evaluation.)*"
    )
    response_body = (
        response
        if has_response
        else "*(No text supplied for this role in this evaluation.)*"
    )
    parts.append(f"## Text in prompt role\n\n{prompt_body}\n\n")
    parts.append(f"## Text in response role\n\n{response_body}\n\n")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def build_evaluation_prompt_single_criterion(
    prompt: str,
    response: str,
    criterion: "CriterionDefinition",
    *,
    has_prompt: bool,
    has_response: bool,
    system_prompt: str | None = None,
    contexts: list[str] | None = None,
    prompt_descriptor: str | None = None,
    response_descriptor: str | None = None,
) -> str:
    """Build a prompt that asks the judge LLM to score a single criterion only."""
    lines = [
        f"**{criterion.name}** — {criterion.description}",
    ]
    if criterion.evaluation_prompt:
        lines.append(f"Guidance: {criterion.evaluation_prompt}")
    if criterion.score_descriptors:
        descriptors_str = ", ".join(
            f"{k}: {v}" for k, v in sorted(criterion.score_descriptors.items())
        )
        lines.append(f"Score descriptors: {descriptors_str}")
    criteria_block = "\n".join(lines)

    system_prompt_section = (
        f"## System Prompt\n\n{system_prompt}\n\n" if system_prompt else ""
    )
    submission_section = _format_submission_sections(
        has_prompt=has_prompt,
        has_response=has_response,
        prompt=prompt,
        response=response,
        prompt_descriptor=prompt_descriptor,
        response_descriptor=response_descriptor,
    )
    context_section = (
        f"## Additional Context\n\n{_render_context_section(contexts)}\n\n"
        if contexts
        else ""
    )

    assess_line = (
        f'  "assessability": "{ASSESSABILITY_ASSESSED}" or '
        f'"{ASSESSABILITY_NOT_ASSESSABLE}",\n'
        f'  "score": <1–5 when assessability is "{ASSESSABILITY_ASSESSED}"; '
        f'omit or null when "{ASSESSABILITY_NOT_ASSESSABLE}">,\n'
        '  "reasoning": "<concise justification; if not assessable, explain why>"\n'
    )
    json_rules = (
        f"When `assessability` is `{ASSESSABILITY_ASSESSED}`, `score` must be a number "
        f"from 1 (very poor) to 5 (excellent). When `assessability` is "
        f"`{ASSESSABILITY_NOT_ASSESSABLE}`, do not treat `score` as a real rating "
        "(omit it or set null)."
    )

    if criterion.evaluation_steps:
        numbered_steps = "\n".join(
            f"{i + 1}. {step}" for i, step in enumerate(criterion.evaluation_steps)
        )
        step_count = len(criterion.evaluation_steps)
        step_key_example = json.dumps(
            ["<answer to step " + str(i + 1) + ">" for i in range(step_count)]
        )
        return f"""You are an expert evaluator. Assess exactly **one** criterion for the submitted material below.

{_JUDGE_META_INSTRUCTIONS}
{system_prompt_section}{submission_section}{context_section}## Criterion to Score

{criteria_block}

## Evaluation Steps

Work through each step in order before providing your final assessment:

{numbered_steps}

Return a **single JSON object** — no other text, no markdown code fences:

{{
  "step_reasoning": {step_key_example},
{assess_line}}}

Rules: {json_rules}
"""

    return f"""You are an expert evaluator. Assess exactly **one** criterion for the submitted material below.

{_JUDGE_META_INSTRUCTIONS}
{system_prompt_section}{submission_section}{context_section}## Criterion to Score

{criteria_block}

Return a **single JSON object** — no other text, no markdown code fences:

{{
{assess_line}}}

Rules: {json_rules}
"""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def parse_single_criterion_response(
    raw_text: str,
    criterion_name: str,
    judge_model: str,
    provider: str,
) -> tuple[str, float | None, str]:
    """Parse the judge LLM's raw output for a single-criterion evaluation.

    Returns:
        Tuple of (assessability, score or None, reasoning).

    Raises:
        ProviderError: If the response cannot be parsed or required keys are missing.
    """
    from src.errors import ProviderError

    cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Failed to parse single-criterion judge response as JSON",
            extra={
                "criterion_name": criterion_name,
                "error": str(exc),
                "judge_model": judge_model,
                "provider": provider,
            },
        )
        raise ProviderError(
            f"Failed to parse judge response for criterion '{criterion_name}' as JSON: {exc}. "
            f"Raw (first 200 chars): {raw_text[:200]!r}"
        ) from exc

    assessability = data.get("assessability")
    if assessability not in (ASSESSABILITY_ASSESSED, ASSESSABILITY_NOT_ASSESSABLE):
        if assessability is None and "score" in data:
            assessability = ASSESSABILITY_ASSESSED
        else:
            raise ProviderError(
                f"Judge response for criterion '{criterion_name}' must include "
                f"'assessability' as '{ASSESSABILITY_ASSESSED}' or "
                f"'{ASSESSABILITY_NOT_ASSESSABLE}'. Keys found: {list(data.keys())}"
            )

    base_reasoning: str = data.get("reasoning", "").strip() or "(no reasoning provided)"

    step_reasoning = data.get("step_reasoning")
    if step_reasoning and isinstance(step_reasoning, list):
        steps_str = "\n".join(
            f"Step {i + 1}: {s}" for i, s in enumerate(step_reasoning)
        )
        reasoning = f"{steps_str}\n\nFinal: {base_reasoning}"
    else:
        reasoning = base_reasoning

    if assessability == ASSESSABILITY_NOT_ASSESSABLE:
        return (ASSESSABILITY_NOT_ASSESSABLE, None, reasoning)

    if "score" not in data:
        raise ProviderError(
            f"Judge response for criterion '{criterion_name}' is missing 'score' "
            f"when assessability is '{ASSESSABILITY_ASSESSED}'. "
            f"Keys found: {list(data.keys())}"
        )

    try:
        score = float(data["score"])
    except (TypeError, ValueError):
        raise ProviderError(
            f"Judge response for criterion '{criterion_name}' has invalid score: "
            f"{data['score']!r}"
        ) from None

    score = max(1.0, min(5.0, score))
    return (ASSESSABILITY_ASSESSED, score, reasoning)


def build_summary_prompt(
    prompt: str,
    response: str,
    results: list[tuple[str, str, float | None, str]],
    *,
    has_prompt: bool,
    has_response: bool,
    system_prompt: str | None = None,
    contexts: list[str] | None = None,
    prompt_descriptor: str | None = None,
    response_descriptor: str | None = None,
) -> str:
    """Build a prompt that asks the judge LLM to synthesise all criterion results."""
    criterion_blocks: list[str] = []
    for name, assessability, score, reasoning in results:
        if assessability == ASSESSABILITY_NOT_ASSESSABLE or score is None:
            criterion_blocks.append(f"### {name} (not assessable)\n{reasoning}")
        else:
            criterion_blocks.append(
                f"### {name} (score: {score}/5)\n{reasoning}"
            )
    criteria_section = "\n\n".join(criterion_blocks)

    system_prompt_section = (
        f"## System Prompt\n\n{system_prompt}\n\n" if system_prompt else ""
    )
    submission_section = _format_submission_sections(
        has_prompt=has_prompt,
        has_response=has_response,
        prompt=prompt,
        response=response,
        prompt_descriptor=prompt_descriptor,
        response_descriptor=response_descriptor,
    )
    context_section = (
        f"## Additional Context\n\n{_render_context_section(contexts)}\n\n"
        if contexts
        else ""
    )

    return f"""You are an expert evaluator. All per-criterion evaluation results are provided below.
Write a concise 総評 (executive summary) in Japanese that synthesises the findings.

{_JUDGE_META_INSTRUCTIONS}
{system_prompt_section}{submission_section}{context_section}## Per-Criterion Results

{criteria_section}

## Instructions

- Synthesise key strengths and weaknesses across all criteria in 3–5 sentences.
- Reference specific criterion names. For criteria marked **not assessable**, do not invent a numeric score; mention the limitation only.
- For assessed criteria, you may reference scores where helpful.
- Do NOT state an overall numeric aggregate score.
- Return only the summary text in Japanese, with no headings or extra formatting.
"""


def aggregate_results(
    results: list[tuple[str, str, float | None, str]],
    reasoning: str,
    judge_model: str,
    provider: str,
) -> dict:
    """Combine per-criterion results into the response dict.

    Args:
        results: ``(name, assessability, score, reasoning)`` per criterion, in
            the order the criteria file declared them.
        reasoning: The synthesised executive summary (総評).
        judge_model: Model that produced the judgements.
        provider: Provider that served the model.

    Returns:
        Dict matching ``contracts/lambda-response.json``. Criteria marked
        ``not_assessable`` are omitted from ``criterion_scores`` but retain their
        entry in ``criterion_reasoning`` and ``criterion_assessability``.
    """
    criterion_assessability = {name: a for name, a, _, _ in results}
    criterion_scores = {
        name: s
        for name, a, s, _ in results
        if a == ASSESSABILITY_ASSESSED and s is not None
    }
    criterion_reasoning = {name: r for name, _, _, r in results}

    return {
        "criterion_scores": criterion_scores,
        "criterion_reasoning": criterion_reasoning,
        "criterion_assessability": criterion_assessability,
        "reasoning": reasoning,
        "judge_model": judge_model,
        "provider": provider,
    }


# ---------------------------------------------------------------------------
# Single-criterion evaluation
# ---------------------------------------------------------------------------


# capture_response=False keeps the judge's reasoning — which quotes the
# submitted material — out of X-Ray metadata.
@tracer.capture_method(capture_response=False)
def _evaluate_one_criterion(
    criterion: "CriterionDefinition",
    prompt: str,
    response: str,
    *,
    has_prompt: bool,
    has_response: bool,
    prompt_descriptor: str | None,
    response_descriptor: str | None,
    provider: "BaseProvider",
    model: str,
    timeout: int,
    provider_label: str,
    system_prompt: str | None = None,
    contexts: list[str] | None = None,
) -> tuple[str, str, float | None, str]:
    """Evaluate a single criterion: build prompt, call LLM, parse response."""
    judge_prompt = build_evaluation_prompt_single_criterion(
        prompt,
        response,
        criterion,
        has_prompt=has_prompt,
        has_response=has_response,
        system_prompt=system_prompt,
        contexts=contexts,
        prompt_descriptor=prompt_descriptor,
        response_descriptor=response_descriptor,
    )
    llm_start = time.perf_counter()
    raw_text = provider.complete(
        messages=[{"role": "user", "content": judge_prompt}],
        model=model,
        timeout=timeout,
    )
    llm_duration_ms = round((time.perf_counter() - llm_start) * 1000)
    add_latency_ms(MetricName.JUDGE_LATENCY_MS, llm_duration_ms)
    if llm_duration_ms >= _LLM_DURATION_LOG_THRESHOLD_MS:
        logger.info(
            "Judge LLM call completed (single criterion)",
            extra={
                "criterion_name": criterion.name,
                "model": model,
                "duration_ms": llm_duration_ms,
            },
        )
    assessability, score, reasoning = parse_single_criterion_response(
        raw_text,
        criterion_name=criterion.name,
        judge_model=model,
        provider=provider_label,
    )
    return (criterion.name, assessability, score, reasoning)
