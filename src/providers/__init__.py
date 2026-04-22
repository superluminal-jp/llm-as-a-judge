"""LLM provider protocol, factory, and cold-start cache.

Each provider is initialised once per Lambda container lifetime and reused
across invocations to avoid repeated SDK client construction and connection
pool setup.

Usage::

    from src.providers import get_provider

    provider = get_provider("anthropic", config)
    text = provider.complete(messages, model="claude-sonnet-4-6", timeout=30)

Supported provider names: ``"anthropic"``, ``"openai"``, ``"bedrock"``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from aws_lambda_powertools import Logger

if TYPE_CHECKING:
    from src.config import Config

logger = Logger(service="llm-judge")

# ---------------------------------------------------------------------------
# Provider protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class BaseProvider(Protocol):
    """Structural interface for LLM provider clients.

    All provider implementations must expose a synchronous :meth:`complete`
    method that sends a list of messages to the underlying LLM and returns
    the raw text of the model's response.
    """

    def complete(
        self,
        messages: list[dict],
        model: str,
        timeout: int,
    ) -> str:
        """Send messages to the LLM and return the raw text response.

        Args:
            messages: Conversation history as a list of
                      ``{"role": str, "content": str}`` dicts.
            model:    Model name or ID accepted by the provider's API.
            timeout:  Request timeout in seconds.

        Returns:
            Raw text content extracted from the LLM's response.

        Raises:
            ProviderError: If the API call fails for any reason (auth,
                rate limit, network timeout, unexpected response format).
        """
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Cold-start cache
# ---------------------------------------------------------------------------

# Cold-start: provider instances cached per Lambda container. Keys are
# provider names (e.g. "anthropic"). Instances are created lazily on first
# use and reused for all subsequent invocations in the same container.
_cache: dict[str, BaseProvider] = {}


def get_provider(name: str, config: "Config") -> BaseProvider:
    """Return a cached provider instance, creating it on first call.

    Args:
        name:   Provider identifier — one of ``"anthropic"``, ``"openai"``,
                or ``"bedrock"``.
        config: Application configuration used to initialise the client
                (API keys, timeout, etc.).

    Returns:
        A :class:`BaseProvider`-compatible provider instance.

    Raises:
        ConfigurationError: If ``name`` is not a recognised provider.
    """
    if name not in _cache:
        _cache[name] = _create(name, config)
        logger.debug("Provider created and cached", extra={"provider": name})
    return _cache[name]


def _create(name: str, config: "Config") -> BaseProvider:
    """Instantiate the provider implementation for the given name.

    Args:
        name:   Provider identifier.
        config: Application configuration.

    Returns:
        Newly created provider instance.

    Raises:
        ConfigurationError: If ``name`` does not map to a known provider.
    """
    from src.handler import ConfigurationError

    if name == "anthropic":
        from src.providers.anthropic import AnthropicProvider

        return AnthropicProvider(config)
    if name == "openai":
        from src.providers.openai import OpenAIProvider

        return OpenAIProvider(config)
    if name == "bedrock":
        from src.providers.bedrock import BedrockProvider

        return BedrockProvider(config)

    raise ConfigurationError(
        f"Unknown provider '{name}'. "
        "Supported providers: 'anthropic', 'openai', 'bedrock'."
    )
