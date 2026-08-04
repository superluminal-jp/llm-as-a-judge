"""Map step: score exactly one criterion.

Runs once per criterion, in parallel branches bounded by the Map state's
``MaxConcurrency``. Reads the staged job payload by claim check and delegates to
:func:`src.evaluator._evaluate_one_criterion`, so the judge prompt and parsing
are the same code the rest of the service uses.

Two things keep this step cheap to run at volume:

* **Idempotency.** The judge call is keyed on the evaluation's content hash plus
  the criterion and model, so a Map retry or a resubmitted request returns the
  stored result instead of paying for the model again.
* **Result offloading.** The reasoning text goes to S3 and only a pointer is
  returned. Step Functions caps inter-state data at 256 KB, which a few hundred
  criteria would otherwise breach in aggregate even though no single result is
  large.

This handler does not retry. Retries are declared on the Map state, so backoff
happens between Lambda invocations rather than inside billed execution time.
"""

from __future__ import annotations

import os
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from src.config import get_config
from src.criteria import load_from_dict
from src.errors import ValidationError
from src.evaluator import _evaluate_one_criterion
from src.idempotency import build_key, idempotent_criterion_call
from src.jobs import get_job, put_result
from src.observability import MetricName, add_count, metrics, tracer
from src.providers import get_provider

logger = Logger(service="llm-judge")


@idempotent_criterion_call
def _score_criterion(*, payload: dict[str, Any]) -> dict[str, Any]:
    """Run the judge call for one criterion and store its result in S3.

    Decorated so that a repeat of the same ``payload["idempotency_key"]``
    returns the previously stored return value without calling the model. The
    S3 key is derived from the same content hash, so the cached return value
    keeps pointing at a real object.

    Args:
        payload: ``{"idempotency_key", "job_uri", "criterion_index"}``.

    Returns:
        ``{"name", "assessability", "score", "result_uri"}``.
    """
    job = get_job(payload["job_uri"])
    criteria = load_from_dict(job["criteria"])
    criterion = criteria.criteria[payload["criterion_index"]]

    provider_name: str = job["provider"]
    judge_model: str = job["judge_model"]
    config = get_config()
    provider = get_provider(provider_name, config)

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

    result_uri = put_result(
        os.environ.get("JOBS_BUCKET", ""),
        job["content_hash"],
        name,
        {
            "name": name,
            "assessability": assessability,
            "score": score,
            "reasoning": reasoning,
        },
    )

    # Only the pointer and the small scalar fields cross the state boundary;
    # the reasoning text stays in S3.
    return {
        "name": name,
        "assessability": assessability,
        "score": score,
        "result_uri": result_uri,
    }


@tracer.capture_lambda_handler(capture_response=False)
@logger.inject_lambda_context(log_event=False)
def handler(event: dict, context: LambdaContext) -> dict[str, Any]:
    """Score one criterion of a staged evaluation job.

    Args:
        event:   ``{"job_uri": str, "criterion_index": int}`` — one Map item
                 produced by :mod:`src.handlers.prepare`.
        context: Lambda context provided by the runtime.

    Returns:
        ``{"name", "assessability", "score", "result_uri"}``. ``score`` is
        ``None`` when the criterion is not assessable; the reasoning text lives
        at ``result_uri``.

    Raises:
        ValidationError: If the event does not carry a usable job URI or index.
        ProviderError:   If the judge LLM call fails or its output cannot be
            parsed.
    """
    request_id = getattr(context, "aws_request_id", None)
    if request_id:
        logger.set_correlation_id(request_id)

    job_uri = event.get("job_uri")
    if not isinstance(job_uri, str) or not job_uri:
        raise ValidationError("Map item is missing a 'job_uri' string.")

    criterion_index = event.get("criterion_index")
    # bool is a subclass of int; True must not be accepted as index 1.
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

    metrics.add_dimension(name="provider", value=provider_name)
    metrics.add_dimension(name="judge_model", value=judge_model)
    tracer.put_annotation(key="criterion", value=criterion.name)

    try:
        return _score_criterion(
            payload={
                "idempotency_key": build_key(
                    job["content_hash"], criterion.name, judge_model
                ),
                "job_uri": job_uri,
                "criterion_index": criterion_index,
            }
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
