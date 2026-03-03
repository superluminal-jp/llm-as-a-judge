"""Synchronous OpenAI provider for LLM-as-a-Judge.

Wraps the OpenAI Python SDK to expose a :class:`~src.providers.BaseProvider`-
compatible :meth:`~OpenAIProvider.complete` method. The underlying HTTP client
is constructed once per Lambda container lifetime and reused across invocations.

The SDK's built-in retry mechanism (``max_retries=3``) handles transient
network errors without additional wrappers.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import openai
from aws_lambda_powertools import Logger

if TYPE_CHECKING:
    from src.config import Config

logger = Logger(service="llm-judge")


class OpenAIProvider:
    """Synchronous OpenAI Chat Completions API client.

    Attributes:
        _client: OpenAI SDK client instance, initialised at construction
                 time and reused for all calls.
    """

    def __init__(self, config: "Config") -> None:
        """Initialise the OpenAI client.

        Args:
            config: Application configuration containing the API key and
                    request timeout.
        """
        # Cold-start: OpenAI client initialized once per Lambda container.
        # The SDK maintains an internal HTTP connection pool that is reused
        # across Lambda invocations within the same container.
        self._client = openai.OpenAI(
            api_key=config.openai_api_key,
            max_retries=3,
        )
        logger.debug("OpenAIProvider initialised")

    def complete(
        self,
        messages: list[dict],
        model: str,
        timeout: int,
    ) -> str:
        """Send messages to the OpenAI API and return the text response.

        Args:
            messages: Conversation history as a list of
                      ``{"role": str, "content": str}`` dicts.
            model:    OpenAI model identifier (e.g. ``"gpt-4o"``).
            timeout:  Request timeout in seconds.

        Returns:
            Raw text content from the first choice message.

        Raises:
            ProviderError: If the API call fails due to authentication issues,
                rate limiting, or any other API error.
        """
        from src.handler import ProviderError

        start = time.perf_counter()
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=messages,
                timeout=timeout,
            )
            text: str = response.choices[0].message.content
            duration_ms = round((time.perf_counter() - start) * 1000)
            logger.debug(
                "OpenAI API call succeeded",
                extra={
                    "model": model,
                    "response_length": len(text),
                    "duration_ms": duration_ms,
                },
            )
            return text

        except openai.APITimeoutError as exc:
            duration_ms = round((time.perf_counter() - start) * 1000)
            logger.error(
                "OpenAI API request timed out",
                extra={"model": model, "timeout_sec": timeout, "duration_ms": duration_ms},
                exc_info=True,
            )
            raise ProviderError(
                f"OpenAI API request timed out after {timeout}s. Retry or increase timeout."
            ) from exc

        except openai.AuthenticationError as exc:
            logger.error(
                "Authentication failed for OpenAI API",
                extra={"model": model},
                exc_info=True,
            )
            raise ProviderError(
                "Authentication error: check OPENAI_API_KEY."
            ) from exc

        except openai.RateLimitError as exc:
            logger.error(
                "Rate limit exceeded for OpenAI API",
                extra={"model": model},
                exc_info=True,
            )
            raise ProviderError(
                "Rate limit exceeded for OpenAI API. Retry after a delay."
            ) from exc

        except openai.APIError as exc:
            logger.error(
                "OpenAI API error",
                extra={"model": model, "error": str(exc)},
                exc_info=True,
            )
            raise ProviderError(
                f"OpenAI API error: {exc}"
            ) from exc
