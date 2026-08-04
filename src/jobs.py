"""Claim-check storage for evaluation job payloads.

Step Functions caps the data flowing between states at 256 KB. The submitted
prompt, response, and retrieval contexts routinely exceed that for document-scale
evaluations, and copying them into every parallel Map branch would multiply the
problem by the criteria count.

So the payload is written to S3 once by the prepare step, and only a short
``s3://`` URI travels through the state machine. Each branch reads the payload
back. This is the standard claim-check pattern for Step Functions payload
limits.

Job objects are transient. The bucket carries a lifecycle rule that expires
them, so nothing here deletes objects explicitly — a failed execution leaves its
payload behind for debugging until the rule collects it.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

import boto3
import botocore.exceptions
from aws_lambda_powertools import Logger

logger = Logger(service="llm-judge")

# Cold-start: S3 client initialised once per Lambda container and reused, which
# also reuses the underlying HTTP connection pool.
_s3_client = boto3.client("s3")

# Container-level cache of fetched job payloads. Every Map branch for a given
# execution reads the same object, and Lambda reuses containers across branches,
# so this removes most of the redundant GetObject calls. Bounded because a warm
# container serves many executions over its lifetime.
_JOB_CACHE_MAX_ENTRIES = 8
_job_cache: dict[str, dict[str, Any]] = {}

_S3_URI_PATTERN = re.compile(r"^s3://([^/]+)/(.+)$")


def _parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """Split ``s3://bucket/key`` into its bucket and key parts.

    Args:
        s3_uri: URI of the form ``s3://<bucket>/<key>``.

    Returns:
        Tuple of ``(bucket, key)``.

    Raises:
        ValidationError: If the URI does not match the expected format.
    """
    from src.handler import ValidationError

    match = _S3_URI_PATTERN.match(s3_uri)
    if not match:
        raise ValidationError(
            f"Invalid job URI '{s3_uri}'. Expected format: s3://<bucket>/<key>"
        )
    return match.group(1), match.group(2)


def put_job(bucket: str, payload: dict[str, Any]) -> str:
    """Write an evaluation job payload to S3 and return its claim-check URI.

    Args:
        bucket:  Name of the jobs bucket (``JOBS_BUCKET`` environment variable).
        payload: JSON-serialisable job payload.

    Returns:
        The ``s3://`` URI of the stored object.

    Raises:
        ConfigurationError: If ``bucket`` is empty or the write is denied.
        LlmJudgeError:      If the object cannot be written for any other reason.
    """
    from src.handler import ConfigurationError, LlmJudgeError

    if not bucket:
        raise ConfigurationError(
            "JOBS_BUCKET environment variable is not set. The Step Functions "
            "workflow needs a bucket to stage evaluation payloads in."
        )

    key = f"jobs/{uuid.uuid4()}.json"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    try:
        _s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
        )
    except botocore.exceptions.ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.error(
            "Failed to stage evaluation job payload",
            extra={"bucket": bucket, "key": key, "error_code": error_code},
            exc_info=True,
        )
        if error_code in ("AccessDenied", "403"):
            raise ConfigurationError(
                f"Lambda execution role lacks s3:PutObject on s3://{bucket}/{key}"
            ) from exc
        raise LlmJudgeError(
            f"Failed to stage evaluation job payload [{error_code}]"
        ) from exc

    job_uri = f"s3://{bucket}/{key}"
    logger.debug(
        "Evaluation job staged",
        extra={"job_uri": job_uri, "payload_bytes": len(body)},
    )
    return job_uri


def get_job(job_uri: str) -> dict[str, Any]:
    """Read an evaluation job payload back from its claim-check URI.

    Results are cached per Lambda container, so the parallel Map branches that
    share an execution do not each pay for a GetObject.

    Args:
        job_uri: URI previously returned by :func:`put_job`.

    Returns:
        The stored job payload.

    Raises:
        ValidationError:   If the URI is malformed.
        ConfigurationError: If reading is denied.
        LlmJudgeError:     If the object is missing or is not valid JSON.
    """
    from src.handler import ConfigurationError, LlmJudgeError

    cached = _job_cache.get(job_uri)
    if cached is not None:
        return cached

    bucket, key = _parse_s3_uri(job_uri)

    try:
        response = _s3_client.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read().decode("utf-8")
    except botocore.exceptions.ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.error(
            "Failed to read evaluation job payload",
            extra={"job_uri": job_uri, "error_code": error_code},
            exc_info=True,
        )
        if error_code in ("AccessDenied", "403"):
            raise ConfigurationError(
                f"Lambda execution role lacks s3:GetObject on {job_uri}"
            ) from exc
        raise LlmJudgeError(
            f"Evaluation job payload not readable at {job_uri} [{error_code}]"
        ) from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise LlmJudgeError(
            f"Evaluation job payload at {job_uri} is not valid JSON: {exc}"
        ) from exc

    if len(_job_cache) >= _JOB_CACHE_MAX_ENTRIES:
        # Plain FIFO eviction: entries are only useful for the lifetime of one
        # execution, so recency ordering buys nothing over insertion ordering.
        _job_cache.pop(next(iter(_job_cache)))
    _job_cache[job_uri] = payload

    return payload
