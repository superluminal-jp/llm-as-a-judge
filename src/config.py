"""Environment-variable-based configuration for the LLM-as-a-Judge Lambda function.

All settings are read from environment variables at module import time (cold start)
and cached as an immutable :class:`Config` dataclass for the lifetime of the
Lambda container.

Environment Variables:
    DEFAULT_PROVIDER:    LLM provider used when the event does not specify one.
                         One of ``anthropic``, ``openai``, or ``bedrock``.
                         Defaults to ``"bedrock"``.
    ANTHROPIC_API_KEY:   API key for Anthropic. Required when provider is
                         ``"anthropic"``.
    ANTHROPIC_MODEL:     Judge model for Anthropic.
                         Defaults to ``"claude-sonnet-4-6"``.
    OPENAI_API_KEY:      API key for OpenAI. Required when provider is
                         ``"openai"``.
    OPENAI_MODEL:        Judge model for OpenAI.
                         Defaults to ``"gpt-4o"``.
    BEDROCK_MODEL:       Judge model for Bedrock (no API key required; Lambda
                         execution role provides IAM access).
                         Defaults to ``"amazon.nova-lite-v1:0"`` (on-demand
                         throughput available in ap-northeast-1). For Claude
                         models use a cross-region inference profile ARN, e.g.
                         ``ap.anthropic.claude-3-5-sonnet-20241022-v2:0``.
    REQUEST_TIMEOUT:     HTTP request timeout in seconds (integer).
                         Defaults to ``30``.
    LOG_LEVEL:           Powertools log level (``DEBUG``, ``INFO``, …).
                         Defaults to ``"INFO"``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from aws_lambda_powertools import Logger

logger = Logger(service="llm-judge")

# ---------------------------------------------------------------------------
# Config dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    """Immutable application configuration loaded from environment variables.

    All fields are read once per Lambda container lifetime (cold start) and
    never mutated afterwards, which is safe for concurrent Lambda invocations.

    Attributes:
        default_provider:  LLM provider to use when the event omits ``provider``.
        anthropic_api_key: Anthropic API key (empty string when not configured).
        anthropic_model:   Default judge model for Anthropic.
        openai_api_key:    OpenAI API key (empty string when not configured).
        openai_model:      Default judge model for OpenAI.
        bedrock_model:     Default judge model for Bedrock.
        request_timeout:   HTTP request timeout in seconds.
        log_level:         Powertools log level string.
    """

    default_provider: str
    anthropic_api_key: str
    anthropic_model: str
    openai_api_key: str
    openai_model: str
    bedrock_model: str
    request_timeout: int
    log_level: str


# ---------------------------------------------------------------------------
# Cold-start cache
# ---------------------------------------------------------------------------

# Cold-start: initialized once per Lambda container. Subsequent invocations
# within the same container reuse this instance without re-reading env vars.
_config: Config | None = None


def get_config() -> Config:
    """Return the cached :class:`Config`, creating it on first call.

    This function is safe to call multiple times per invocation; it always
    returns the same instance created during the cold start.

    Returns:
        Populated :class:`Config` with values from environment variables.
    """
    global _config
    if _config is None:
        _config = _load_config()
        logger.debug(
            "Config loaded from environment",
            extra={
                "default_provider": _config.default_provider,
                "request_timeout": _config.request_timeout,
            },
        )
    return _config


def _load_config() -> Config:
    """Read all environment variables and construct a :class:`Config`.

    Returns:
        A new :class:`Config` instance populated from ``os.environ``.
    """
    try:
        request_timeout = int(os.environ.get("REQUEST_TIMEOUT", "30"))
    except ValueError:
        request_timeout = 30

    return Config(
        default_provider=os.environ.get("DEFAULT_PROVIDER", "bedrock"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
        bedrock_model=os.environ.get("BEDROCK_MODEL", "amazon.nova-lite-v1:0"),
        request_timeout=request_timeout,
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )


# ---------------------------------------------------------------------------
# Provider-specific validation
# ---------------------------------------------------------------------------


def validate_for_provider(config: Config, provider: str) -> None:
    """Assert that the required API key is present for the given provider.

    Bedrock uses IAM authentication via the Lambda execution role and therefore
    requires no API key validation here.

    Args:
        config:   Application configuration.
        provider: Provider identifier (``"anthropic"``, ``"openai"``,
                  or ``"bedrock"``).

    Raises:
        ConfigurationError: If the required API key environment variable is
            empty for ``"anthropic"`` or ``"openai"``.
    """
    # Import here to avoid circular dependency (handler imports config).
    from src.handler import ConfigurationError

    if provider == "anthropic" and not config.anthropic_api_key:
        logger.error(
            "Provider validation failed: missing API key",
            extra={"provider": provider, "missing_config": "ANTHROPIC_API_KEY"},
        )
        raise ConfigurationError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Configure it via AWS Secrets Manager or Lambda environment variables."
        )
    if provider == "openai" and not config.openai_api_key:
        logger.error(
            "Provider validation failed: missing API key",
            extra={"provider": provider, "missing_config": "OPENAI_API_KEY"},
        )
        raise ConfigurationError(
            "OPENAI_API_KEY environment variable is not set. "
            "Configure it via AWS Secrets Manager or Lambda environment variables."
        )
    # Bedrock: no API key required — Lambda execution role provides IAM access.
