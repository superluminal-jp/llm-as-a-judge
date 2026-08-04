"""Prepare step: validate the request and stage it for parallel evaluation.

First state of the Step Functions workflow. Performs everything that must happen
exactly once — input validation, criteria resolution, provider/model selection —
then writes the resulting payload to S3 and returns the claim-check URI plus one
Map item per criterion.

Reuses :func:`src.validation.validate_event` and the loaders in
:mod:`src.criteria`, so validation happens once per evaluation rather than once
per criterion.
"""

from __future__ import annotations

import dataclasses
import os
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from src.config import get_config, validate_for_provider
from src.criteria import DefaultCriteria, load_from_s3
from src.jobs import compute_content_hash, put_job
from src.observability import metrics, tracer
from src.validation import default_model, normalize_context, validate_event

logger = Logger(service="llm-judge")


@tracer.capture_lambda_handler(capture_response=False)
@logger.inject_lambda_context(log_event=False)
def handler(event: dict, context: LambdaContext) -> dict[str, Any]:
    """Validate the evaluation request and stage it in S3.

    Args:
        event:   Same schema as the direct-invoke Lambda event; see
                 ``contracts/lambda-event.json``.
        context: Lambda context provided by the runtime.

    Returns:
        Dict with ``job_uri``, ``content_hash``, ``provider``, ``judge_model``,
        ``criteria_count`` and ``items`` — the last being the array the Map
        state iterates.

    Raises:
        ValidationError:    Required fields missing or malformed.
        ConfigurationError: Required environment variables not set.
        CriteriaLoadError:  S3 criteria file not accessible or invalid JSON.
    """
    request_id = getattr(context, "aws_request_id", None)
    if request_id:
        logger.set_correlation_id(request_id)

    prompt_text, response_text, prompt_descriptor, response_descriptor = (
        validate_event(event)
    )

    config = get_config()

    provider_name: str = event.get("provider") or config.default_provider
    judge_model: str = event.get("judge_model") or default_model(config, provider_name)
    validate_for_provider(config, provider_name)

    criteria_file: str | None = event.get("criteria_file")
    if criteria_file:
        logger.info("Loading criteria from S3", extra={"criteria_file": criteria_file})
        criteria = load_from_s3(criteria_file)
    else:
        criteria = DefaultCriteria.balanced()

    metrics.add_dimension(name="provider", value=provider_name)
    metrics.add_dimension(name="judge_model", value=judge_model)
    tracer.put_annotation(key="provider", value=provider_name)
    tracer.put_annotation(key="judge_model", value=judge_model)

    job_payload = {
        "prompt": prompt_text,
        "response": response_text,
        "prompt_descriptor": prompt_descriptor,
        "response_descriptor": response_descriptor,
        "system_prompt": event.get("system_prompt") or None,
        "contexts": normalize_context(event.get("contexts")),
        "has_prompt": bool(prompt_text),
        "has_response": bool(response_text),
        "provider": provider_name,
        "judge_model": judge_model,
        # dataclasses.asdict produces exactly the keys src.criteria.load_from_dict
        # reads back, so the round trip needs no bespoke serialiser.
        "criteria": dataclasses.asdict(criteria),
    }

    # Hashed before staging so that the hash covers only what determines the
    # outcome — the job's own UUID must not enter it, or two identical
    # submissions would never deduplicate.
    job_payload["content_hash"] = compute_content_hash(job_payload)

    job_uri = put_job(os.environ.get("JOBS_BUCKET", ""), job_payload)

    logger.info(
        "Evaluation prepared",
        extra={
            "job_uri": job_uri,
            "content_hash": job_payload["content_hash"],
            "provider": provider_name,
            "model": judge_model,
            "criteria_count": len(criteria.criteria),
        },
    )

    return {
        "job_uri": job_uri,
        "content_hash": job_payload["content_hash"],
        "provider": provider_name,
        "judge_model": judge_model,
        "criteria_count": len(criteria.criteria),
        # One Map item per criterion. Only the index travels; the criterion
        # definition itself stays in the staged payload.
        "items": [
            {"job_uri": job_uri, "criterion_index": index}
            for index in range(len(criteria.criteria))
        ],
    }
