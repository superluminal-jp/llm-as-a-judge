"""Summarize step: synthesise the 総評 and assemble the final response.

Last state of the workflow. Receives one pointer per criterion, fetches the
results from S3, restores the criteria file's ordering, asks the judge for an
executive summary, and assembles the response.

The Map state hands over pointers rather than reasoning text so that the state
size stays independent of the criteria count — see :mod:`src.jobs`. Fetching
them back is concurrent, since a few hundred sequential round trips would
dominate this step's runtime.

The assembled dict is what ``contracts/lambda-response.json`` describes; it is
produced by :func:`src.evaluator.aggregate_results`.
"""

from __future__ import annotations

import os
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from src.config import get_config
from src.criteria import load_from_dict
from src.errors import ValidationError
from src.evaluator import (
    ASSESSABILITY_NOT_ASSESSABLE,
    aggregate_results,
    build_summary_prompt,
)
from src.jobs import get_job, get_results, put_final_result
from src.observability import MetricName, add_count, metrics, tracer
from src.providers import get_provider

logger = Logger(service="llm-judge")


@tracer.capture_lambda_handler(capture_response=False)
@logger.inject_lambda_context(log_event=False)
def handler(event: dict, context: LambdaContext) -> dict[str, Any]:
    """Aggregate per-criterion results into the final evaluation response.

    Args:
        event:   ``{"job_uri": str, "results": [...]}`` where each result is a
                 pointer dict emitted by :mod:`src.handlers.evaluate_criterion`
                 carrying ``result_uri``.
        context: Lambda context provided by the runtime.

    Returns:
        Evaluation result dict matching ``contracts/lambda-response.json``.

    Raises:
        ValidationError: If the event is missing the job URI or results.
        ProviderError:   If the summary LLM call fails.
    """
    request_id = getattr(context, "aws_request_id", None)
    if request_id:
        logger.set_correlation_id(request_id)

    job_uri = event.get("job_uri")
    if not isinstance(job_uri, str) or not job_uri:
        raise ValidationError("Summarize input is missing a 'job_uri' string.")

    raw_results = event.get("results")
    if not isinstance(raw_results, list) or not raw_results:
        raise ValidationError(
            "Summarize input is missing a non-empty 'results' array."
        )

    job = get_job(job_uri)
    criteria = load_from_dict(job["criteria"])
    provider_name: str = job["provider"]
    judge_model: str = job["judge_model"]

    # The Map output carries pointers; the reasoning text is in S3.
    missing = [r for r in raw_results if not r.get("result_uri")]
    if missing:
        raise ValidationError(
            f"{len(missing)} criterion result(s) are missing 'result_uri'."
        )
    fetched = get_results([r["result_uri"] for r in raw_results])

    # Map branches complete in arbitrary order. Restore the criteria file's
    # ordering so that the summary prompt — and the response — read in the order
    # the rubric author intended.
    order = {c.name: i for i, c in enumerate(criteria.criteria)}
    results: list[tuple[str, str, float | None, str]] = [
        (r["name"], r["assessability"], r.get("score"), r["reasoning"])
        for r in fetched
    ]
    results.sort(key=lambda r: order.get(r[0], len(order)))

    config = get_config()
    provider = get_provider(provider_name, config)

    metrics.add_dimension(name="provider", value=provider_name)
    metrics.add_dimension(name="judge_model", value=judge_model)

    summary_prompt = build_summary_prompt(
        job["prompt"],
        job["response"],
        results,
        has_prompt=job["has_prompt"],
        has_response=job["has_response"],
        system_prompt=job.get("system_prompt"),
        contexts=job.get("contexts"),
        prompt_descriptor=job.get("prompt_descriptor"),
        response_descriptor=job.get("response_descriptor"),
    )
    reasoning = provider.complete(
        messages=[{"role": "user", "content": summary_prompt}],
        model=judge_model,
        timeout=config.request_timeout,
    )

    not_assessable = sum(
        1 for _, assessability, _, _ in results
        if assessability == ASSESSABILITY_NOT_ASSESSABLE
    )
    if not_assessable:
        add_count(MetricName.NOT_ASSESSABLE_COUNT, not_assessable)
    add_count(MetricName.EVALUATIONS_COMPLETED)

    logger.info(
        "Evaluation completed",
        extra={
            "provider": provider_name,
            "model": judge_model,
            "criteria_count": len(results),
            "not_assessable": not_assessable,
        },
    )

    response = aggregate_results(
        results,
        reasoning=reasoning,
        judge_model=judge_model,
        provider=provider_name,
    )

    # Persisted on both paths: the synchronous workflow returns this to its
    # caller, but an asynchronous execution has nowhere to return it to, so S3
    # is where an async caller collects it. The URI rides along in the execution
    # output without becoming part of the response contract.
    result_uri = put_final_result(
        os.environ.get("JOBS_BUCKET", ""), job["content_hash"], response
    )
    logger.info("Evaluation result stored", extra={"result_uri": result_uri})

    return response
