"""Map step: score exactly one criterion.

Runs once per criterion, in parallel branches bounded by the Map state's
``MaxConcurrency``. Reads the staged job payload by claim check and delegates to
:func:`src.evaluator._evaluate_one_criterion` — the same function the
direct-invoke handler runs inside its thread pool, so both paths build identical
judge prompts and parse responses identically.

This handler does not retry. Retries are declared on the Map state, so backoff
happens between Lambda invocations rather than inside billed execution time.
"""

from __future__ import annotations

from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from src.config import get_config
from src.criteria import load_from_dict
from src.evaluator import _evaluate_one_criterion
from src.jobs import get_job
from src.observability import MetricName, add_count, metrics, tracer
from src.providers import get_provider

logger = Logger(service="llm-judge")


@tracer.capture_lambda_handler(capture_response=False)
@logger.inject_lambda_context(log_event=False)
def handler(event: dict, context: LambdaContext) -> dict[str, Any]:
    """Score one criterion of a staged evaluation job.

    Args:
        event:   ``{"job_uri": str, "criterion_index": int}`` — one Map item
                 produced by :mod:`src.handlers.prepare`.
        context: Lambda context provided by the runtime.

    Returns:
        ``{"name", "assessability", "score", "reasoning"}``. ``score`` is
        ``None`` when the criterion is not assessable.

    Raises:
        ValidationError: If the event does not carry a usable job URI or index.
        ProviderError:   If the judge LLM call fails or its output cannot be
            parsed.
    """
    from src.handler import ValidationError

    request_id = getattr(context, "aws_request_id", None)
    if request_id:
        logger.set_correlation_id(request_id)

    job_uri = event.get("job_uri")
    if not isinstance(job_uri, str) or not job_uri:
        raise ValidationError("Map item is missing a 'job_uri' string.")

    criterion_index = event.get("criterion_index")
    if not isinstance(criterion_index, int) or isinstance(criterion_index, bool):
        raise ValidationError("Map item is missing an integer 'criterion_index'.")

    job = get_job(job_uri)
    criteria = load_from_dict(job["criteria"])

    if not 0 <= criterion_index < len(criteria.criteria):
        raise ValidationError(
            f"criterion_index {criterion_index} is out of range for a criteria "
            f"set of {len(criteria.criteria)}."
        )

    criterion = criteria.criteria[criterion_index]
    provider_name: str = job["provider"]
    judge_model: str = job["judge_model"]

    config = get_config()
    provider = get_provider(provider_name, config)

    metrics.add_dimension(name="provider", value=provider_name)
    metrics.add_dimension(name="judge_model", value=judge_model)
    tracer.put_annotation(key="criterion", value=criterion.name)

    try:
        name, assessability, score, reasoning = _evaluate_one_criterion(
            criterion,
            job["prompt"],
            job["response"],
            has_prompt=job["has_prompt"],
            has_response=job["has_response"],
            prompt_descriptor=job.get("prompt_descriptor"),
            response_descriptor=job.get("response_descriptor"),
            provider=provider,
            model=judge_model,
            timeout=config.request_timeout,
            provider_label=provider_name,
            system_prompt=job.get("system_prompt"),
            contexts=job.get("contexts"),
        )
    except Exception as exc:
        add_count(MetricName.CRITERION_EVALUATION_FAILED)
        logger.error(
            "Criterion evaluation failed",
            extra={
                "criterion_name": criterion.name,
                "criterion_index": criterion_index,
                "model": judge_model,
                "error_type": type(exc).__name__,
            },
        )
        raise

    return {
        "name": name,
        "assessability": assessability,
        "score": score,
        "reasoning": reasoning,
    }
