"""Synchronous Anthropic provider for LLM-as-a-Judge.

Wraps the Anthropic Python SDK to expose a :class:`BaseProvider`-compatible
:meth:`~AnthropicProvider.complete` method. The underlying HTTP client is
constructed once per Lambda container lifetime and reused across invocations.

The SDK's built-in retry mechanism (``max_retries=3``) handles transient
network errors without additional retry wrappers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import anthropic
from aws_lambda_powertools import Logger

if TYPE_CHECKING:
    from src.config import Config

logger = Logger(service="llm-judge")


class AnthropicProvider:
    """Synchronous Anthropic Messages API client.

    Attributes:
        _client: Anthropic SDK client instance, initialised at construction
                 time and reused for all calls.
    """

    def __init__(self, config: "Config") -> None:
        """Initialise the Anthropic client.

        Args:
            config: Application configuration containing the API key and
                    request timeout.
        """
        # Cold-start: Anthropic client initialized once per container.
        # The SDK maintains an internal HTTP connection pool that is reused
        # across Lambda invocations within the same container.
        self._client = anthropic.Anthropic(
            api_key=config.anthropic_api_key,
            max_retries=3,
        )
        logger.debug("AnthropicProvider initialised")

    def complete(
        self,
        messages: list[dict],
        model: str,
        timeout: int,
    ) -> str:
        """Send messages to the Anthropic API and return the text response.

        Args:
            messages: Conversation history as a list of
                      ``{"role": str, "content": str}`` dicts.
            model:    Anthropic model identifier (e.g. ``"claude-sonnet-4-6"``).
            timeout:  Request timeout in seconds.

        Returns:
            Raw text content from the first content block of the response.

        Raises:
            ProviderError: If the API call fails due to authentication issues,
                rate limiting, or any other API error.
        """
        from src.handler import ProviderError

        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=4096,
                messages=messages,
                timeout=timeout,
            )
            text: str = response.content[0].text
            logger.debug(
                "Anthropic API call succeeded",
                extra={"model": model, "response_length": len(text)},
            )
            return text

        except anthropic.AuthenticationError as exc:
            logger.error(
                "Authentication failed for Anthropic API",
                extra={"model": model},
                exc_info=True,
            )
            raise ProviderError(
                "Authentication error: check ANTHROPIC_API_KEY."
            ) from exc

        except anthropic.RateLimitError as exc:
            logger.error(
                "Rate limit exceeded for Anthropic API",
                extra={"model": model},
                exc_info=True,
            )
            raise ProviderError(
                "Rate limit exceeded for Anthropic API. Retry after a delay."
            ) from exc

        except anthropic.APIError as exc:
            logger.error(
                "Anthropic API error",
                extra={"model": model, "error": str(exc)},
                exc_info=True,
            )
            raise ProviderError(
                f"Anthropic API error: {exc}"
            ) from exc
