"""Claim-check storage for evaluation payloads and per-criterion results.

Step Functions caps the data flowing between states at 256 KB. Both directions
of the workflow can exceed it:

* **Inbound.** The submitted prompt, response, and retrieval contexts routinely
  run to document scale, and copying them into every parallel Map branch would
  multiply that by the criteria count.
* **Outbound.** Each criterion returns reasoning text — more of it when
  ``evaluation_steps`` are defined — so a few hundred criteria overflow the
  limit even though no single result is large.

So payloads and results are written to S3 and only short ``s3://`` URIs travel
through the state machine. This is the standard claim-check pattern for Step
Functions payload limits, and it makes the state size independent of both the
submission size and the criteria count.

Result keys are **deterministic**: they derive from a hash of the evaluation
inputs, so re-running the same criterion overwrites its own object rather than
accumulating copies. The same hash is what the idempotency layer keys on (see
:mod:`src.idempotency`), which keeps the stored object and the cached result
pointing at each other.

Objects are transient. The bucket carries lifecycle rules that expire them, so
nothing here deletes anything explicitly — a failed execution leaves its payload
behind for debugging until the rule collects it.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
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

# Fields that determine an evaluation's outcome. Anything outside this set — the
# job's own UUID, for instance — must not affect the hash, or identical
# submissions would never deduplicate.
_CONTENT_HASH_FIELDS = (
    "prompt",
    "response",
    "prompt_descriptor",
    "response_descriptor",
    "system_prompt",
    "contexts",
    "provider",
    "judge_model",
    "criteria",
)

# Concurrency for fetching per-criterion results in the summarize step. These
# are small S3 GETs, not model calls, so the limit exists only to avoid opening
# an unbounded number of sockets when the criteria count is large.
_RESULT_FETCH_WORKERS = 16


def _parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """Split ``s3://bucket/key`` into its bucket and key parts.

    Args:
        s3_uri: URI of the form ``s3://<bucket>/<key>``.

    Returns:
        Tuple of ``(bucket, key)``.

    Raises:
        ValidationError: If the URI does not match the expected format.
    """
    from src.errors import ValidationError

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
    from src.errors import ConfigurationError, LlmJudgeError

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
    from src.errors import ConfigurationError, LlmJudgeError

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


# ---------------------------------------------------------------------------
# Content hashing
# ---------------------------------------------------------------------------


def compute_content_hash(payload: dict[str, Any]) -> str:
    """Return a stable hash of the fields that determine an evaluation's outcome.

    Two requests that would produce the same judgement hash the same, which is
    what lets :mod:`src.idempotency` skip a repeat model call and what makes
    result keys deterministic. Fields outside :data:`_CONTENT_HASH_FIELDS` — the
    job UUID in particular — are excluded so that resubmitting identical content
    is recognised as identical.

    Args:
        payload: The staged job payload.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    canonical = {field: payload.get(field) for field in _CONTENT_HASH_FIELDS}
    # sort_keys makes the encoding independent of dict insertion order, which
    # otherwise varies with how the payload was built.
    encoded = json.dumps(
        canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def result_key(content_hash: str, criterion_name: str) -> str:
    """Return the deterministic S3 key for one criterion's result."""
    return f"results/{content_hash}/{criterion_name}.json"


# ---------------------------------------------------------------------------
# Per-criterion results
# ---------------------------------------------------------------------------


def put_result(
    bucket: str,
    content_hash: str,
    criterion_name: str,
    result: dict[str, Any],
) -> str:
    """Store one criterion's result and return its ``s3://`` URI.

    The key is deterministic, so a retried criterion overwrites its own object
    instead of leaving an orphan behind.

    Args:
        bucket:         Jobs bucket name (``JOBS_BUCKET``).
        content_hash:   Hash from :func:`compute_content_hash`.
        criterion_name: Criterion this result belongs to.
        result:         JSON-serialisable per-criterion result.

    Returns:
        The ``s3://`` URI of the stored object.

    Raises:
        ConfigurationError: If ``bucket`` is empty or the write is denied.
        LlmJudgeError:      If the object cannot be written for any other reason.
    """
    from src.errors import ConfigurationError, LlmJudgeError

    if not bucket:
        raise ConfigurationError(
            "JOBS_BUCKET environment variable is not set. The workflow needs a "
            "bucket to store per-criterion results in."
        )

    key = result_key(content_hash, criterion_name)
    body = json.dumps(result, ensure_ascii=False).encode("utf-8")

    try:
        _s3_client.put_object(
            Bucket=bucket, Key=key, Body=body, ContentType="application/json"
        )
    except botocore.exceptions.ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.error(
            "Failed to store criterion result",
            extra={"bucket": bucket, "key": key, "error_code": error_code},
            exc_info=True,
        )
        if error_code in ("AccessDenied", "403"):
            raise ConfigurationError(
                f"Lambda execution role lacks s3:PutObject on s3://{bucket}/{key}"
            ) from exc
        raise LlmJudgeError(
            f"Failed to store criterion result [{error_code}]"
        ) from exc

    return f"s3://{bucket}/{key}"


def get_result(result_uri: str) -> dict[str, Any]:
    """Read one criterion's result back from its URI.

    Args:
        result_uri: URI previously returned by :func:`put_result`.

    Returns:
        The stored per-criterion result.

    Raises:
        ValidationError:    If the URI is malformed.
        ConfigurationError: If reading is denied.
        LlmJudgeError:      If the object is missing or is not valid JSON.
    """
    from src.errors import ConfigurationError, LlmJudgeError

    bucket, key = _parse_s3_uri(result_uri)

    try:
        response = _s3_client.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read().decode("utf-8")
    except botocore.exceptions.ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.error(
            "Failed to read criterion result",
            extra={"result_uri": result_uri, "error_code": error_code},
            exc_info=True,
        )
        if error_code in ("AccessDenied", "403"):
            raise ConfigurationError(
                f"Lambda execution role lacks s3:GetObject on {result_uri}"
            ) from exc
        raise LlmJudgeError(
            f"Criterion result not readable at {result_uri} [{error_code}]"
        ) from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise LlmJudgeError(
            f"Criterion result at {result_uri} is not valid JSON: {exc}"
        ) from exc


def get_results(result_uris: list[str]) -> list[dict[str, Any]]:
    """Read many criterion results, preserving the order of ``result_uris``.

    Fetches concurrently because the summarize step would otherwise pay one
    round trip per criterion in sequence — noticeable once the criteria count
    reaches the hundreds this design is meant to support. These are small S3
    GETs, so threads are the right tool here even though the criteria fan-out
    itself deliberately is not.

    Args:
        result_uris: URIs returned by :func:`put_result`.

    Returns:
        Results in the same order as ``result_uris``.

    Raises:
        LlmJudgeError: If any result cannot be read. A missing result means the
            summary would silently omit a criterion, so this does not degrade.
    """
    if not result_uris:
        return []
    if len(result_uris) == 1:
        return [get_result(result_uris[0])]

    workers = min(len(result_uris), _RESULT_FETCH_WORKERS)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        # executor.map preserves input order and re-raises the first exception.
        return list(executor.map(get_result, result_uris))


# ---------------------------------------------------------------------------
# Final evaluation result
# ---------------------------------------------------------------------------


def put_final_result(
    bucket: str, content_hash: str, result: dict[str, Any]
) -> str:
    """Persist the assembled evaluation response and return its ``s3://`` URI.

    The synchronous workflow returns the response to its caller directly, but an
    asynchronous execution has nowhere to return it to — so it is always written
    here and the URI is reported in the execution output. Writing it on both
    paths keeps one code path and gives the synchronous caller a durable copy.

    Args:
        bucket:       Jobs bucket name (``JOBS_BUCKET``).
        content_hash: Hash from :func:`compute_content_hash`.
        result:       The assembled response.

    Returns:
        The ``s3://`` URI of the stored object.

    Raises:
        ConfigurationError: If ``bucket`` is empty or the write is denied.
        LlmJudgeError:      If the object cannot be written for any other reason.
    """
    from src.errors import ConfigurationError, LlmJudgeError

    if not bucket:
        raise ConfigurationError(
            "JOBS_BUCKET environment variable is not set. The workflow needs a "
            "bucket to store the final evaluation result in."
        )

    key = f"final/{content_hash}.json"
    body = json.dumps(result, ensure_ascii=False).encode("utf-8")

    try:
        _s3_client.put_object(
            Bucket=bucket, Key=key, Body=body, ContentType="application/json"
        )
    except botocore.exceptions.ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.error(
            "Failed to store final evaluation result",
            extra={"bucket": bucket, "key": key, "error_code": error_code},
            exc_info=True,
        )
        if error_code in ("AccessDenied", "403"):
            raise ConfigurationError(
                f"Lambda execution role lacks s3:PutObject on s3://{bucket}/{key}"
            ) from exc
        raise LlmJudgeError(
            f"Failed to store final evaluation result [{error_code}]"
        ) from exc

    return f"s3://{bucket}/{key}"
