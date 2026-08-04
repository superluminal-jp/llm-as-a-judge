"""Idempotency for per-criterion judge calls.

Each evaluation costs N+1 model calls. At the volumes this service is built for,
the duplicates are what hurt: a Map state retry, a client resubmitting after a
timeout, or a replayed queue message all re-run work whose answer is already
known, and every one of those is billed by the model provider.

So the per-criterion judge call is made idempotent. The key is the content hash
of the evaluation inputs combined with the criterion and model — not the job
URI, which is unique per execution and would therefore never match anything.
Two identical submissions deduplicate; changing the prompt, the criteria, or the
model does not.

Scope
    Only the criterion step is wrapped. The prepare step is cheap and its output
    embeds a fresh job URI, and the summarize step's cost is a single call whose
    input already depends on every criterion result.

Opt-out
    With ``IDEMPOTENCY_TABLE`` unset the decorator is a pass-through, so local
    runs and the test suite need no DynamoDB. That is a deliberate degradation
    to "always evaluate", never to "silently return something stale".
"""

from __future__ import annotations

import os
from typing import Any, Callable

from aws_lambda_powertools import Logger

logger = Logger(service="llm-judge")

# How long a stored result satisfies a repeat request. Long enough to absorb
# retries and same-day resubmissions; short enough that a model or prompt change
# is not shadowed by stale entries for long. Must stay below the jobs bucket's
# result retention, or a cached hit could point at an expired S3 object.
DEFAULT_EXPIRY_SECONDS = 24 * 60 * 60


def is_enabled() -> bool:
    """Return whether an idempotency table is configured."""
    return bool(os.environ.get("IDEMPOTENCY_TABLE", "").strip())


def idempotent_criterion_call(func: Callable[..., Any]) -> Callable[..., Any]:
    """Make a per-criterion evaluation idempotent on its ``payload`` argument.

    The wrapped function must accept a keyword argument named ``payload``
    containing an ``idempotency_key`` field.

    Args:
        func: Function performing the judge call for one criterion.

    Returns:
        The function unchanged when no table is configured, otherwise a wrapper
        that returns the stored result for a repeated key.
    """
    table_name = os.environ.get("IDEMPOTENCY_TABLE", "").strip()
    if not table_name:
        logger.debug(
            "Idempotency disabled: IDEMPOTENCY_TABLE is not set. "
            "Every criterion will be evaluated."
        )
        return func

    # Imported lazily so that deployments without idempotency never construct a
    # DynamoDB client they will not use.
    from aws_lambda_powertools.utilities.idempotency import (
        DynamoDBPersistenceLayer,
        IdempotencyConfig,
        idempotent_function,
    )

    try:
        expiry = int(
            os.environ.get("IDEMPOTENCY_EXPIRY_SECONDS", str(DEFAULT_EXPIRY_SECONDS))
        )
    except ValueError:
        expiry = DEFAULT_EXPIRY_SECONDS

    persistence_layer = DynamoDBPersistenceLayer(table_name=table_name)
    config = IdempotencyConfig(
        event_key_jmespath="idempotency_key",
        expires_after_seconds=expiry,
        # A missing key would silently disable deduplication for that call,
        # which is exactly the failure mode this exists to prevent.
        raise_on_no_idempotency_key=True,
        # Repeated keys within one warm container skip DynamoDB entirely.
        use_local_cache=True,
    )

    logger.debug(
        "Idempotency enabled",
        extra={"table": table_name, "expires_after_seconds": expiry},
    )

    return idempotent_function(
        func,
        data_keyword_argument="payload",
        config=config,
        persistence_store=persistence_layer,
    )


def build_key(content_hash: str, criterion_name: str, judge_model: str) -> str:
    """Return the idempotency key for one criterion of one evaluation.

    Args:
        content_hash:   Hash of the evaluation inputs, from
            :func:`src.jobs.compute_content_hash`.
        criterion_name: Criterion being scored.
        judge_model:    Model producing the judgement — part of the key because
            the same submission judged by a different model is a different
            result.

    Returns:
        Opaque key string.
    """
    return f"{content_hash}:{criterion_name}:{judge_model}"
