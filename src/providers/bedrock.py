"""Synchronous Amazon Bedrock provider for LLM-as-a-Judge.

Uses the Bedrock Runtime ``converse`` API via boto3. Authentication is provided
by the Lambda execution role — no API key is required. The boto3 client is
constructed once per Lambda container lifetime and reused across invocations.

The ``converse`` API provides a provider-agnostic message interface compatible
with all Bedrock foundation models, including Amazon Nova and Anthropic Claude.
"""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING

import boto3
import botocore.exceptions
from aws_lambda_powertools import Logger

if TYPE_CHECKING:
    from src.config import Config

logger = Logger(service="llm-judge")


class BedrockProvider:
    """Synchronous Bedrock Runtime client using the Converse API.

    Attributes:
        _client: boto3 ``bedrock-runtime`` client, initialised once at
                 construction time and reused for all calls.
    """

    def __init__(self, config: "Config") -> None:
        """Initialise the Bedrock Runtime client.

        Args:
            config: Application configuration (used for retry count and
                    region/timeout context; Bedrock uses IAM auth from the
                    execution role).
        """
        # Cold-start: Bedrock client initialized once per Lambda container.
        # IAM credentials are obtained from the Lambda execution role via the
        # instance metadata service, which is also cached by botocore.
        self._client = boto3.client("bedrock-runtime")
        self._max_retries = config.max_retries
        logger.debug("BedrockProvider initialised")

    def complete(
        self,
        messages: list[dict],
        model: str,
        timeout: int,
    ) -> str:
        """Send messages to a Bedrock foundation model and return the text response.

        Converts the standard ``{"role", "content"}`` message format to the
        Bedrock Converse API schema and extracts the text from the response.

        Args:
            messages: Conversation history as a list of
                      ``{"role": str, "content": str}`` dicts.
            model:    Bedrock model ID (e.g. ``"amazon.nova-premier-v1:0"``).
            timeout:  Unused — Bedrock timeout is configured at the botocore
                      session level. Accepted for interface compatibility.

        Returns:
            Raw text content from the first content block of the response.

        Raises:
            ProviderError: If the Bedrock API call fails (throttling, model
                not found, permission denied, etc.).
        """
        from src.handler import ProviderError

        # Convert to Bedrock Converse API message format.
        bedrock_messages = [
            {"role": msg["role"], "content": [{"text": msg["content"]}]}
            for msg in messages
        ]

        # Retryable error codes: ThrottlingException and AccessDeniedException
        # caused by cross-region inference profile routing transient failures.
        _RETRYABLE = frozenset({"ThrottlingException", "AccessDeniedException"})
        _BASE_DELAY = 1.0
        max_retries = self._max_retries

        start = time.perf_counter()
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                response = self._client.converse(
                    modelId=model,
                    messages=bedrock_messages,
                )
                text: str = response["output"]["message"]["content"][0]["text"]
                duration_ms = round((time.perf_counter() - start) * 1000)
                logger.debug(
                    "Bedrock converse call succeeded",
                    extra={
                        "model": model,
                        "response_length": len(text),
                        "duration_ms": duration_ms,
                        "attempt": attempt,
                    },
                )
                return text

            except TimeoutError as exc:
                duration_ms = round((time.perf_counter() - start) * 1000)
                logger.error(
                    "Bedrock API request timed out",
                    extra={"model": model, "duration_ms": duration_ms},
                    exc_info=True,
                )
                raise ProviderError(
                    "Bedrock API request timed out. Retry or increase read_timeout in "
                    "botocore config."
                ) from exc

            except botocore.exceptions.ClientError as exc:
                error_code = exc.response["Error"]["Code"]
                error_message = exc.response["Error"]["Message"]
                if error_code in _RETRYABLE and attempt < max_retries:
                    delay = _BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.warning(
                        "Bedrock transient error, retrying",
                        extra={
                            "model": model,
                            "error_code": error_code,
                            "attempt": attempt,
                            "retry_delay_s": round(delay, 2),
                        },
                    )
                    time.sleep(delay)
                    last_exc = exc
                    continue
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
                raise ProviderError(
                    f"Bedrock API error [{error_code}]: {error_message}"
                ) from exc

        # Exhausted retries
        raise ProviderError(
            f"Bedrock API failed after {max_retries} retries"
        ) from last_exc
