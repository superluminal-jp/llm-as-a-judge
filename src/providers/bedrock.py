"""Synchronous Amazon Bedrock provider for LLM-as-a-Judge.

Uses the Bedrock Runtime ``converse`` API via boto3. Authentication is provided
by the Lambda execution role — no API key is required. The boto3 client is
constructed once per Lambda container lifetime and reused across invocations.

The ``converse`` API provides a provider-agnostic message interface compatible
with all Bedrock foundation models, including Amazon Nova and Anthropic Claude.

Client configuration
    The client is built with an explicit :class:`botocore.config.Config` rather
    than botocore defaults, for three reasons:

    * **Timeouts.** ``REQUEST_TIMEOUT`` previously had no effect on Bedrock —
      botocore's 60-second default read timeout applied instead, which matched
      the old Lambda timeout exactly, so the function was killed before its own
      timeout could produce a diagnosable error.
    * **Retries.** ``adaptive`` mode adds client-side rate limiting on top of
      exponential backoff, which suits a throttling-prone workload far better
      than the ``legacy`` default. It also replaces the hand-rolled retry loop
      this module used to carry, which blocked in ``time.sleep`` on billed
      Lambda time and — incorrectly — retried ``AccessDeniedException``, an
      error that never becomes transient.
    * **Connection pool.** The evaluator issues one concurrent call per
      criterion. botocore's default pool of 10 connections throttled the
      10-criterion criteria file at the HTTP layer, so the pool is sized from
      ``MAX_PARALLEL_CRITERIA``.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import boto3
import botocore.config
import botocore.exceptions
from aws_lambda_powertools import Logger

from src.observability import MetricName, add_count

if TYPE_CHECKING:
    from src.config import Config

logger = Logger(service="llm-judge")

# Connection-pool floor. Keeps small deployments from being pool-bound even
# when MAX_PARALLEL_CRITERIA is set low.
_MIN_POOL_CONNECTIONS = 10

# Connect timeouts should be short — a slow TCP handshake indicates a network
# problem, not a slow model — while read timeouts track the model's think time.
_MAX_CONNECT_TIMEOUT_SEC = 10

# Error codes that indicate the caller is over quota rather than misconfigured.
# botocore retries these internally; by the time one surfaces here, retries are
# exhausted and the caller needs to back off or raise its quota.
_THROTTLING_CODES = frozenset(
    {"ThrottlingException", "TooManyRequestsException", "ServiceQuotaExceededException"}
)


class BedrockProvider:
    """Synchronous Bedrock Runtime client using the Converse API.

    Attributes:
        _client: boto3 ``bedrock-runtime`` client, initialised once at
                 construction time and reused for all calls.
    """

    def __init__(self, config: "Config") -> None:
        """Initialise the Bedrock Runtime client.

        Args:
            config: Application configuration. ``request_timeout`` drives the
                    botocore socket timeouts and ``max_parallel_criteria``
                    sizes the connection pool. Bedrock itself authenticates
                    with IAM credentials from the execution role.
        """
        client_config = botocore.config.Config(
            read_timeout=config.request_timeout,
            connect_timeout=min(_MAX_CONNECT_TIMEOUT_SEC, config.request_timeout),
            # Adaptive mode layers client-side rate limiting over exponential
            # backoff, which is what Bedrock throttling calls for.
            retries={"max_attempts": 5, "mode": "adaptive"},
            max_pool_connections=max(
                _MIN_POOL_CONNECTIONS, config.max_parallel_criteria
            ),
        )

        # Cold-start: Bedrock client initialized once per Lambda container.
        # IAM credentials are obtained from the Lambda execution role via the
        # instance metadata service, which is also cached by botocore.
        self._client = boto3.client("bedrock-runtime", config=client_config)
        logger.debug(
            "BedrockProvider initialised",
            extra={
                "read_timeout": config.request_timeout,
                "max_pool_connections": client_config.max_pool_connections,
            },
        )

    def complete(
        self,
        messages: list[dict],
        model: str,
        timeout: int,
    ) -> str:
        """Send messages to a Bedrock foundation model and return the text response.

        Converts the standard ``{"role", "content"}`` message format to the
        Bedrock Converse API schema and extracts the text from the response.

        Retries are handled by botocore using the adaptive retry mode configured
        in :meth:`__init__`; this method does not retry.

        Args:
            messages: Conversation history as a list of
                      ``{"role": str, "content": str}`` dicts.
            model:    Bedrock model ID or cross-region inference profile ID
                      (e.g. ``"amazon.nova-lite-v1:0"``,
                      ``"jp.anthropic.claude-sonnet-4-6"``).
            timeout:  Accepted for interface compatibility. The effective
                      timeout is the ``read_timeout`` set on the client at
                      construction time, since botocore configures socket
                      timeouts per client rather than per request.

        Returns:
            Raw text content from the first content block of the response.

        Raises:
            ProviderError: If the Bedrock API call fails (throttling, model not
                found, permission denied, malformed response, timeout).
        """
        from src.handler import ProviderError

        # Convert to Bedrock Converse API message format.
        bedrock_messages = [
            {"role": msg["role"], "content": [{"text": msg["content"]}]}
            for msg in messages
        ]

        start = time.perf_counter()
        try:
            response = self._client.converse(
                modelId=model,
                messages=bedrock_messages,
            )
        except (
            botocore.exceptions.ReadTimeoutError,
            botocore.exceptions.ConnectTimeoutError,
            TimeoutError,
        ) as exc:
            duration_ms = round((time.perf_counter() - start) * 1000)
            logger.error(
                "Bedrock API request timed out",
                extra={"model": model, "duration_ms": duration_ms},
                exc_info=True,
            )
            raise ProviderError(
                f"Bedrock request for model '{model}' timed out. Increase "
                "REQUEST_TIMEOUT (and the Lambda timeout alongside it) or "
                "reduce the size of the submitted text."
            ) from exc

        except botocore.exceptions.ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            error_message = exc.response["Error"]["Message"]
            duration_ms = round((time.perf_counter() - start) * 1000)
            logger.error(
                "Bedrock API error",
                extra={
                    "model": model,
                    "error_code": error_code,
                    "duration_ms": duration_ms,
                },
                exc_info=True,
            )

            if error_code in _THROTTLING_CODES:
                add_count(MetricName.BEDROCK_THROTTLED)
                raise ProviderError(
                    f"Bedrock throttled the request for model '{model}' and "
                    f"client-side retries were exhausted [{error_code}]: "
                    f"{error_message}. Lower MAX_PARALLEL_CRITERIA or request a "
                    "quota increase."
                ) from exc

            if error_code == "AccessDeniedException":
                # Not transient: almost always a missing grant. A cross-region
                # inference profile ID needs InvokeModel on both the profile
                # ARN and the underlying model in each routed region.
                raise ProviderError(
                    f"Bedrock denied access to model '{model}' [{error_code}]: "
                    f"{error_message}. Check that the execution role grants "
                    "bedrock:InvokeModel on this model — for a cross-region "
                    "inference profile that means both the inference-profile "
                    "ARN and the foundation-model ARN in every routed region — "
                    "and that model access is enabled in this account."
                ) from exc

            raise ProviderError(
                f"Bedrock API error [{error_code}]: {error_message}"
            ) from exc

        try:
            text: str = response["output"]["message"]["content"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.error(
                "Bedrock response had an unexpected shape",
                extra={"model": model},
                exc_info=True,
            )
            raise ProviderError(
                f"Bedrock response for model '{model}' did not contain a text "
                f"content block: {exc}"
            ) from exc

        duration_ms = round((time.perf_counter() - start) * 1000)
        logger.debug(
            "Bedrock converse call succeeded",
            extra={
                "model": model,
                "response_length": len(text),
                "duration_ms": duration_ms,
            },
        )
        return text
