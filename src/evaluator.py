"""Core evaluation logic for multi-criteria LLM assessment.

Evaluates each criterion independently in parallel (one LLM call per criterion),
then returns per-criterion scores and an executive summary (総評). No score
aggregation is applied.

Pipeline:
    1. :func:`build_evaluation_prompt_single_criterion` — one prompt per criterion.
    2. :func:`_evaluate_one_criterion` — one LLM call per criterion (thread pool).
    3. :func:`parse_single_criterion_response` — score + reasoning per criterion.
    4. :func:`evaluate` — aggregate into criterion_scores and 総評 reasoning.
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from aws_lambda_powertools import Logger

if TYPE_CHECKING:
    from src.criteria import CriterionDefinition, EvaluationCriteria
    from src.providers import BaseProvider

logger = Logger(service="llm-judge")

# Threshold in milliseconds above which LLM call duration is logged at INFO.
_LLM_DURATION_LOG_THRESHOLD_MS = 100

# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def build_evaluation_prompt_single_criterion(
    prompt: str,
    response: str,
    criterion: "CriterionDefinition",
) -> str:
    """Build a prompt that asks the judge LLM to score a single criterion only.

    Used for parallel evaluation: one LLM call per criterion, returning
    ``score`` and ``reasoning`` for that dimension only.

    Args:
        prompt:    The original question given to the evaluated LLM.
        response:  The LLM output to evaluate.
        criterion: Single criterion definition (name, description, etc.).

    Returns:
        Formatted prompt string for a single-criterion evaluation.
    """
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

    if criterion.evaluation_steps:
        numbered_steps = "\n".join(
            f"{i + 1}. {step}" for i, step in enumerate(criterion.evaluation_steps)
        )
        step_count = len(criterion.evaluation_steps)
        return f"""You are an expert evaluator assessing one dimension of an AI-generated response.

## Original Prompt

{prompt}

## Response to Evaluate

{response}

## Criterion to Score

{criteria_block}

## Evaluation Steps

Work through each step in order before providing your final score:

{numbered_steps}

Score this criterion only on an integer scale from 1 (very poor) to 5 (excellent).
Return a **single JSON object** — no other text, no markdown code fences:

{{
  "step_reasoning": {json.dumps(["<answer to step " + str(i + 1) + ">" for i in range(step_count)])},
  "score": <number between 1 and 5, decimals allowed>,
  "reasoning": "<summary justification incorporating the step results>"
}}
"""

    return f"""You are an expert evaluator assessing one dimension of an AI-generated response.

## Original Prompt

{prompt}

## Response to Evaluate

{response}

## Criterion to Score

{criteria_block}

Score this criterion only on an integer scale from 1 (very poor) to 5 (excellent).
Return a **single JSON object** — no other text, no markdown code fences:

{{
  "score": <number between 1 and 5, decimals allowed>,
  "reasoning": "<concise justification for this criterion's score>"
}}
"""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def parse_single_criterion_response(
    raw_text: str,
    criterion_name: str,
    judge_model: str,
    provider: str,
) -> tuple[float, str]:
    """Parse the judge LLM's raw output for a single-criterion evaluation.

    Expects JSON with ``score`` (1–5) and ``reasoning``. Handles Markdown
    code fences.

    Args:
        raw_text:       Raw text returned by the judge LLM.
        criterion_name: Name of the criterion (for error messages).
        judge_model:    Model name (for logging).
        provider:       Provider name (for logging).

    Returns:
        Tuple of (score, reasoning). Score is clamped to [1, 5].

    Raises:
        ProviderError: If the response cannot be parsed or required keys missing.
    """
    from src.handler import ProviderError

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

    if "score" not in data:
        raise ProviderError(
            f"Judge response for criterion '{criterion_name}' is missing 'score'. "
            f"Keys found: {list(data.keys())}"
        )

    try:
        score = float(data["score"])
    except (TypeError, ValueError):
        raise ProviderError(
            f"Judge response for criterion '{criterion_name}' has invalid score: {data['score']!r}"
        ) from None

    score = max(1.0, min(5.0, score))
    base_reasoning: str = data.get("reasoning", "").strip() or "(no reasoning provided)"

    step_reasoning = data.get("step_reasoning")
    if step_reasoning and isinstance(step_reasoning, list):
        steps_str = "\n".join(
            f"Step {i + 1}: {s}" for i, s in enumerate(step_reasoning)
        )
        reasoning = f"{steps_str}\n\nFinal: {base_reasoning}"
    else:
        reasoning = base_reasoning

    return (score, reasoning)


def _build_summary_prompt(
    prompt: str,
    response: str,
    results: list[tuple[str, float, str]],
) -> str:
    """Build a prompt that asks the judge LLM to synthesise all criterion results."""
    criterion_blocks = []
    for name, score, reasoning in results:
        criterion_blocks.append(f"### {name} (score: {score}/5)\n{reasoning}")
    criteria_section = "\n\n".join(criterion_blocks)

    return f"""You are an expert evaluator. All per-criterion evaluation results are provided below.
Write a concise 総評 (executive summary) in Japanese that synthesises the findings.

## Original Prompt

{prompt}

## Response Evaluated

{response}

## Per-Criterion Results

{criteria_section}

## Instructions

- Synthesise key strengths and weaknesses across all criteria in 3–5 sentences.
- Reference specific criterion names and scores where helpful.
- Do NOT state an overall numeric score.
- Return only the summary text in Japanese, with no headings or extra formatting.
"""


def _aggregate_parallel_results(
    results: list[tuple[str, float, str]],
    reasoning: str,
    judge_model: str,
    provider: str,
) -> dict:
    """Combine per-criterion (name, score, reasoning) into the result dict."""
    criterion_scores = {name: score for name, score, _ in results}
    criterion_reasoning = {name: r for name, _, r in results}

    return {
        "criterion_scores": criterion_scores,
        "criterion_reasoning": criterion_reasoning,
        "reasoning": reasoning,
        "judge_model": judge_model,
        "provider": provider,
    }


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def _evaluate_one_criterion(
    criterion: "CriterionDefinition",
    prompt: str,
    response: str,
    provider: "BaseProvider",
    model: str,
    timeout: int,
    provider_label: str,
) -> tuple[str, float, str]:
    """Evaluate a single criterion: build prompt, call LLM, parse response.

    Intended to be run in a thread pool. Returns (criterion_name, score, reasoning).
    """
    judge_prompt = build_evaluation_prompt_single_criterion(
        prompt, response, criterion
    )
    llm_start = time.perf_counter()
    raw_text = provider.complete(
        messages=[{"role": "user", "content": judge_prompt}],
        model=model,
        timeout=timeout,
    )
    llm_duration_ms = round((time.perf_counter() - llm_start) * 1000)
    if llm_duration_ms >= _LLM_DURATION_LOG_THRESHOLD_MS:
        logger.info(
            "Judge LLM call completed (single criterion)",
            extra={
                "criterion_name": criterion.name,
                "model": model,
                "duration_ms": llm_duration_ms,
            },
        )
    score, reasoning = parse_single_criterion_response(
        raw_text,
        criterion_name=criterion.name,
        judge_model=model,
        provider=provider_label,
    )
    return (criterion.name, score, reasoning)


def evaluate(
    prompt: str,
    response: str,
    criteria: "EvaluationCriteria",
    provider: "BaseProvider",
    model: str,
    timeout: int,
    provider_name: str = "",
) -> dict:
    """Run multi-criteria evaluation: one LLM call per criterion in parallel.

    Each criterion is scored independently; results are aggregated into
    criterion_scores and an executive summary (総評). No overall_score is computed.

    Args:
        prompt:        The original question/prompt given to the evaluated LLM.
        response:      The LLM response to evaluate.
        criteria:      Evaluation criteria with names and descriptions.
        provider:      LLM provider client.
        model:         Judge model name/ID.
        timeout:       API request timeout in seconds (per call).
        provider_name: Human-readable provider identifier (optional).

    Returns:
        Dict matching ``contracts/lambda-response.json``
        (criterion_scores, reasoning, judge_model, provider; no overall_score).
    """
    _provider_label = provider_name or provider.__class__.__module__.split(".")[-1]
    criterion_list = criteria.criteria
    order = {c.name: i for i, c in enumerate(criterion_list)}

    with ThreadPoolExecutor(max_workers=len(criterion_list)) as executor:
        futures = {
            executor.submit(
                _evaluate_one_criterion,
                c,
                prompt,
                response,
                provider,
                model,
                timeout,
                _provider_label,
            ): c
            for c in criterion_list
        }
        results: list[tuple[str, float, str]] = []
        for fut in as_completed(futures):
            results.append(fut.result())

    results.sort(key=lambda r: order[r[0]])

    # Generate executive summary (総評) via one additional LLM call.
    summary_prompt = _build_summary_prompt(prompt, response, results)
    llm_start = time.perf_counter()
    reasoning = provider.complete(
        messages=[{"role": "user", "content": summary_prompt}],
        model=model,
        timeout=timeout,
    )
    llm_duration_ms = round((time.perf_counter() - llm_start) * 1000)
    if llm_duration_ms >= _LLM_DURATION_LOG_THRESHOLD_MS:
        logger.info(
            "Judge LLM call completed (summary)",
            extra={"model": model, "duration_ms": llm_duration_ms},
        )

    return _aggregate_parallel_results(
        results, reasoning=reasoning, judge_model=model, provider=_provider_label
    )
