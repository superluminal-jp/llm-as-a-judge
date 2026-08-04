"""Environment-variable-based configuration for the LLM-as-a-Judge Lambda function.

All settings are read from environment variables at module import time (cold start)
and cached as an immutable :class:`Config` dataclass for the lifetime of the
Lambda container.

API keys are **not** expected to live in environment variables in a deployed
stack. The CDK stack provisions a Secrets Manager secret holding a JSON object
with ``ANTHROPIC_API_KEY`` and ``OPENAI_API_KEY`` and passes its name through
``API_KEYS_SECRET_NAME``. :func:`get_api_key` resolves keys lazily — environment
variable first (convenient for local development and tests), then the secret —
and Powertools caches the fetched secret in memory for
``POWERTOOLS_PARAMETERS_MAX_AGE`` seconds (300 by default), so a warm container
does not call Secrets Manager on every invocation.

Bedrock needs no key at all: it authenticates through the Lambda execution role.
The secret is therefore never read when running Bedrock-only.

Environment Variables:
    DEFAULT_PROVIDER:    LLM provider used when the event does not specify one.
                         One of ``anthropic``, ``openai``, or ``bedrock``.
                         Defaults to ``"bedrock"``.
    API_KEYS_SECRET_NAME: Name of the Secrets Manager secret holding a JSON
                         object with ``ANTHROPIC_API_KEY`` / ``OPENAI_API_KEY``.
                         Empty in local development.
    ANTHROPIC_API_KEY:   API key for Anthropic. Overrides the secret when set.
    ANTHROPIC_MODEL:     Judge model for Anthropic.
                         Defaults to ``"claude-sonnet-4-6"``.
    OPENAI_API_KEY:      API key for OpenAI. Overrides the secret when set.
    OPENAI_MODEL:        Judge model for OpenAI.
                         Defaults to ``"gpt-4o"``.
    BEDROCK_MODEL:       Judge model for Bedrock (no API key required; Lambda
                         execution role provides IAM access).
                         Defaults to ``"jp.anthropic.claude-sonnet-4-6"``
                         (JP cross-region inference profile; routes to
                         ap-northeast-1 and ap-northeast-3).
    REQUEST_TIMEOUT:     HTTP/Bedrock request timeout in seconds (integer).
                         Defaults to ``30``.
    MAX_PARALLEL_CRITERIA: Upper bound on concurrent judge LLM calls within a
                         single invocation. Defaults to ``5``.
    LOG_LEVEL:           Powertools log level (``DEBUG``, ``INFO``, …).
                         Defaults to ``"INFO"``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from aws_lambda_powertools import Logger

logger = Logger(service="llm-judge")

# Environment variable holding the API key for each provider, checked before
# falling back to Secrets Manager. Bedrock is absent: it uses IAM auth.
_API_KEY_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}

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
        anthropic_api_key: Anthropic API key read from the environment (empty
                           when the key lives in Secrets Manager instead).
        anthropic_model:   Default judge model for Anthropic.
        openai_api_key:    OpenAI API key read from the environment (empty when
                           the key lives in Secrets Manager instead).
        openai_model:      Default judge model for OpenAI.
        bedrock_model:     Default judge model for Bedrock.
        request_timeout:   HTTP/Bedrock request timeout in seconds.
        log_level:         Powertools log level string.
        api_keys_secret_name: Secrets Manager secret holding the provider API
                           keys as JSON. Empty when unset.
        max_parallel_criteria: Upper bound on concurrent judge LLM calls.
    """

    default_provider: str
    anthropic_api_key: str
    anthropic_model: str
    openai_api_key: str
    openai_model: str
    bedrock_model: str
    request_timeout: int
    log_level: str
    api_keys_secret_name: str = ""
    max_parallel_criteria: int = 5


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
    def _int_env(name: str, default: int) -> int:
        try:
            return int(os.environ.get(name, str(default)))
        except ValueError:
            return default

    return Config(
        default_provider=os.environ.get("DEFAULT_PROVIDER", "bedrock"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
        bedrock_model=os.environ.get("BEDROCK_MODEL", "jp.anthropic.claude-sonnet-4-6"),
        request_timeout=_int_env("REQUEST_TIMEOUT", 30),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        api_keys_secret_name=os.environ.get("API_KEYS_SECRET_NAME", ""),
        max_parallel_criteria=max(1, _int_env("MAX_PARALLEL_CRITERIA", 5)),
    )


# ---------------------------------------------------------------------------
# API key resolution (environment variable → Secrets Manager)
# ---------------------------------------------------------------------------


def get_api_key(config: Config, provider: str) -> str:
    """Return the API key for ``provider``, or an empty string when unavailable.

    Resolution order:

    1. The provider's environment variable, when non-empty. This keeps local
       development and the test suite working without any AWS call.
    2. The JSON secret named by ``API_KEYS_SECRET_NAME``, fetched through
       Powertools ``parameters``, which caches it in memory per container.

    Bedrock is not covered here — it authenticates with the Lambda execution
    role and has no key.

    Args:
        config:   Application configuration.
        provider: Provider identifier (``"anthropic"`` or ``"openai"``).

    Returns:
        The API key, or ``""`` when neither source supplies one.
    """
    env_var = _API_KEY_ENV_VARS.get(provider)
    if env_var is None:
        return ""

    from_env = {
        "anthropic": config.anthropic_api_key,
        "openai": config.openai_api_key,
    }[provider]
    if from_env:
        return from_env

    if not config.api_keys_secret_name:
        return ""

    # Imported lazily so that environments without the secret configured (the
    # Bedrock-only default, and the test suite) never import boto3 clients they
    # will not use.
    from aws_lambda_powertools.utilities import parameters

    try:
        secret = parameters.get_secret(config.api_keys_secret_name, transform="json")
    except Exception as exc:  # noqa: BLE001 — provider-agnostic fallback
        logger.error(
            "Failed to read API keys from Secrets Manager",
            extra={
                "secret_name": config.api_keys_secret_name,
                "provider": provider,
                "error_type": type(exc).__name__,
            },
        )
        return ""

    if not isinstance(secret, dict):
        logger.error(
            "API keys secret is not a JSON object",
            extra={"secret_name": config.api_keys_secret_name},
        )
        return ""

    return str(secret.get(env_var, "") or "")


# ---------------------------------------------------------------------------
# Provider-specific validation
# ---------------------------------------------------------------------------


def validate_for_provider(config: Config, provider: str) -> None:
    """Assert that the required API key is present for the given provider.

    Bedrock uses IAM authentication via the Lambda execution role and therefore
    requires no API key validation here.

    The key is resolved through :func:`get_api_key`, so either an environment
    variable or the Secrets Manager secret satisfies this check.

    Args:
        config:   Application configuration.
        provider: Provider identifier (``"anthropic"``, ``"openai"``,
                  or ``"bedrock"``).

    Raises:
        ConfigurationError: If no API key can be resolved for ``"anthropic"``
            or ``"openai"``.
    """
    # Import here to avoid circular dependency (handler imports config).
    from src.handler import ConfigurationError

    env_var = _API_KEY_ENV_VARS.get(provider)
    if env_var is None:
        # Bedrock: no API key required — Lambda execution role provides IAM access.
        return

    if get_api_key(config, provider):
        return

    logger.error(
        "Provider validation failed: missing API key",
        extra={
            "provider": provider,
            "missing_config": env_var,
            "secret_name": config.api_keys_secret_name or None,
        },
    )
    raise ConfigurationError(
        f"No API key available for provider '{provider}'. Set the {env_var} "
        f"environment variable, or add it to the "
        f"'{config.api_keys_secret_name or '<API_KEYS_SECRET_NAME unset>'}' "
        "secret in AWS Secrets Manager."
    )
