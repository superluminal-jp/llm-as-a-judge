"""Core evaluation logic for multi-criteria LLM assessment.

Builds structured prompts that instruct a judge LLM to score a response
against a set of weighted criteria, calls the provider, parses the JSON
reply, validates criterion coverage, and aggregates scores into a final
weighted average.

Pipeline:
    1. :func:`build_evaluation_prompt` — format criteria + inputs as a prompt.
    2. Provider :meth:`~src.providers.BaseProvider.complete` — call judge LLM.
    3. :func:`parse_evaluation_response` — extract JSON, validate, compute score.
    4. :func:`evaluate` — orchestrate the full pipeline.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from aws_lambda_powertools import Logger

if TYPE_CHECKING:
    from src.criteria import EvaluationCriteria
    from src.providers import BaseProvider

logger = Logger(service="llm-judge")

# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def build_evaluation_prompt(
    prompt: str,
    response: str,
    criteria: "EvaluationCriteria",
) -> str:
    """Construct a structured prompt asking the judge LLM to evaluate a response.

    The prompt instructs the model to score each criterion on a 1–5 scale
    and return a JSON object containing ``criterion_scores`` (keyed by
    criterion name) and a ``reasoning`` field.

    Args:
        prompt:   The original question or instruction given to the evaluated LLM.
        response: The LLM output to be evaluated.
        criteria: Evaluation criteria defining dimension names, descriptions,
                  optional guidance, and weights.

    Returns:
        A fully formatted prompt string ready to be sent to the judge LLM.
    """
    criteria_section_lines: list[str] = []
    for i, criterion in enumerate(criteria.criteria, 1):
        lines = [
            f"{i}. **{criterion.name}** — {criterion.description}",
        ]
        if criterion.evaluation_prompt:
            lines.append(f"   Guidance: {criterion.evaluation_prompt}")
        if criterion.examples:
            examples_str = ", ".join(
                f"{k}: {v}" for k, v in sorted(criterion.examples.items())
            )
            lines.append(f"   Examples: {examples_str}")
        criteria_section_lines.append("\n".join(lines))

    criteria_section = "\n\n".join(criteria_section_lines)
    criterion_names = [c.name for c in criteria.criteria]
    json_keys = ", ".join(f'"{name}": <score>' for name in criterion_names)

    return f"""You are an expert evaluator assessing the quality of an AI-generated response.

## Original Prompt

{prompt}

## Response to Evaluate

{response}

## Evaluation Criteria

Score each criterion on an integer scale from 1 (very poor) to 5 (excellent).

{criteria_section}

## Instructions

Evaluate the response against all criteria above. Return a **single JSON object** with
the following structure — no other text, no markdown code fences:

{{
  "criterion_scores": {{{json_keys}}},
  "reasoning": "<concise overall justification for the scores>"
}}

All criterion names must appear in ``criterion_scores`` exactly as listed above.
Scores must be numbers between 1 and 5 (decimals allowed).
"""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def parse_evaluation_response(
    raw_text: str,
    criteria: "EvaluationCriteria",
    judge_model: str,
    provider: str,
) -> dict:
    """Parse the judge LLM's raw text output into an evaluation result dict.

    Handles JSON wrapped in Markdown code fences (```json ... ```) in addition
    to bare JSON. Validates that every criterion name appears in the returned
    ``criterion_scores`` and computes the weighted overall score.

    Args:
        raw_text:    Raw text returned by the judge LLM.
        criteria:    Evaluation criteria used to build the prompt (for
                     validation and weight computation).
        judge_model: Model name used as judge (stored in the result).
        provider:    Provider name (stored in the result).

    Returns:
        Dict matching ``contracts/lambda-response.json``:
        ``overall_score``, ``criterion_scores``, ``reasoning``,
        ``judge_model``, ``provider``.

    Raises:
        ProviderError: If the text cannot be parsed as JSON, ``criterion_scores``
            is absent, or any expected criterion name is missing.
    """
    from src.handler import ProviderError

    # Strip Markdown code fences if present (```json ... ``` or ``` ... ```).
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Failed to parse judge LLM response as JSON",
            extra={"raw_length": len(raw_text), "error": str(exc)},
        )
        raise ProviderError(
            f"Failed to parse judge response as JSON: {exc}. "
            f"Raw text (first 200 chars): {raw_text[:200]!r}"
        ) from exc

    if "criterion_scores" not in data:
        raise ProviderError(
            "Judge response is missing the 'criterion_scores' key. "
            f"Keys found: {list(data.keys())}"
        )

    criterion_scores: dict = data["criterion_scores"]
    expected_names = {c.name for c in criteria.criteria}
    missing = expected_names - set(criterion_scores.keys())
    if missing:
        raise ProviderError(
            f"Judge response is missing scores for criterion(s): {sorted(missing)}. "
            f"Scores returned: {list(criterion_scores.keys())}"
        )

    reasoning: str = data.get("reasoning", "")

    # Compute weighted overall score.
    weights = criteria.normalised_weights
    overall_score: float = sum(
        float(criterion_scores[name]) * weight
        for name, weight in weights.items()
    )

    logger.debug(
        "Evaluation response parsed",
        extra={
            "overall_score": round(overall_score, 3),
            "criteria_count": len(criterion_scores),
        },
    )

    return {
        "overall_score": round(overall_score, 4),
        "criterion_scores": {k: float(v) for k, v in criterion_scores.items()},
        "reasoning": reasoning,
        "judge_model": judge_model,
        "provider": provider,
    }


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def evaluate(
    prompt: str,
    response: str,
    criteria: "EvaluationCriteria",
    provider: "BaseProvider",
    model: str,
    timeout: int,
    provider_name: str = "",
) -> dict:
    """Run multi-criteria evaluation and return the result dict.

    Orchestrates prompt construction, LLM invocation, and response parsing
    into a single call.

    Args:
        prompt:        The original question/prompt given to the evaluated LLM.
        response:      The LLM response to evaluate.
        criteria:      Evaluation criteria with names, descriptions, and weights.
        provider:      LLM provider client implementing
                       :class:`~src.providers.BaseProvider`.
        model:         Judge model name/ID.
        timeout:       API request timeout in seconds.
        provider_name: Human-readable provider identifier stored in the result
                       (e.g. ``"anthropic"``). Derived from the provider class
                       module name when omitted.

    Returns:
        Dict matching ``contracts/lambda-response.json``.

    Raises:
        ProviderError: If the LLM API call fails or the response cannot be parsed.
    """
    judge_prompt = build_evaluation_prompt(prompt, response, criteria)

    logger.debug(
        "Sending evaluation prompt to judge LLM",
        extra={"model": model, "prompt_length": len(judge_prompt)},
    )

    raw_text = provider.complete(
        messages=[{"role": "user", "content": judge_prompt}],
        model=model,
        timeout=timeout,
    )

    logger.debug(
        "Received raw response from judge LLM",
        extra={"model": model, "response_length": len(raw_text)},
    )

    # Derive provider label from module name when not explicitly provided.
    _provider_label = provider_name or provider.__class__.__module__.split(".")[-1]

    return parse_evaluation_response(
        raw_text, criteria, judge_model=model, provider=_provider_label
    )
