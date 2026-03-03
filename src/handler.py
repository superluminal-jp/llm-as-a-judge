"""AWS Lambda handler for LLM-as-a-Judge evaluation.

Entry point for the Lambda function. Validates the input event, loads evaluation
criteria (default or from S3), and delegates scoring to the evaluator module.

Exception hierarchy defined here is the single source of truth used across all
modules to ensure consistent error propagation.

Modules:
    evaluator: Prompt construction, LLM call, JSON parsing, score aggregation.
    criteria:  EvaluationCriteria data class and S3/dict loaders.
    config:    Environment-variable-based Config with cold-start caching.
    providers: BaseProvider protocol, per-provider implementations, factory.
"""

import time

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from src.config import get_config, validate_for_provider
from src.criteria import DefaultCriteria, load_from_s3
from src.evaluator import evaluate
from src.providers import get_provider

logger = Logger(service="llm-judge")

# Threshold in seconds above which handler duration is logged at INFO.
_DURATION_LOG_THRESHOLD_SEC = 0.1


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class LlmJudgeError(Exception):
    """Base exception for all llm-judge errors."""


class ValidationError(LlmJudgeError):
    """Raised when the input event is invalid (missing fields, bad format)."""


class ConfigurationError(LlmJudgeError):
    """Raised when required environment variables are missing or invalid."""


class ProviderError(LlmJudgeError):
    """Raised when an LLM provider API call fails (auth, rate limit, timeout)."""


class CriteriaLoadError(LlmJudgeError):
    """Raised when criteria cannot be loaded from S3 (not found, invalid JSON)."""


# ---------------------------------------------------------------------------
# Supported providers
# ---------------------------------------------------------------------------

_SUPPORTED_PROVIDERS = frozenset({"anthropic", "openai", "bedrock"})


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------


def _validate_event(event: dict) -> None:
    """Validate that mandatory event fields are present and non-empty.

    Args:
        event: Raw Lambda invocation event dict.

    Raises:
        ValidationError: If ``prompt`` or ``response`` is absent or empty.
    """
    for field in ("prompt", "response"):
        value = event.get(field)
        if not value or not isinstance(value, str) or not value.strip():
            raise ValidationError(
                f"Event field '{field}' is required and must be a non-empty string."
            )

    provider = event.get("provider")
    if provider is not None and provider not in _SUPPORTED_PROVIDERS:
        raise ValidationError(
            f"Unsupported provider '{provider}'. "
            f"Valid values: {sorted(_SUPPORTED_PROVIDERS)}."
        )

    criteria_file = event.get("criteria_file")
    if criteria_file is not None:
        if not isinstance(criteria_file, str) or not criteria_file.startswith("s3://"):
            raise ValidationError(
                "Field 'criteria_file' must be an S3 URI starting with 's3://'."
            )


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


@logger.inject_lambda_context(log_event=False)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Evaluate an LLM response using a judge LLM.

    Orchestrates the full evaluation pipeline:
    1. Validates the input event.
    2. Loads configuration from environment variables.
    3. Resolves the judge LLM provider and model.
    4. Loads evaluation criteria (default or from S3).
    5. Delegates scoring to :func:`~src.evaluator.evaluate`.

    Args:
        event: Lambda invocation event. See ``contracts/lambda-event.json``.
        context: Lambda context object provided by the runtime.

    Returns:
        Evaluation result dict matching ``contracts/lambda-response.json``.

    Raises:
        ValidationError: Required fields missing or malformed.
        ConfigurationError: Required environment variables not set.
        ProviderError: LLM API call failed.
        CriteriaLoadError: S3 criteria file not accessible or invalid JSON.
    """
    start_time = time.perf_counter()
    request_id = getattr(context, "aws_request_id", None)

    try:
        _validate_event(event)

        config = get_config()

        # Resolve provider and model — event fields override env-var defaults.
        provider_name: str = event.get("provider") or config.default_provider
        judge_model: str = event.get("judge_model") or _default_model(
            config, provider_name
        )

        validate_for_provider(config, provider_name)

        # Load evaluation criteria.
        criteria_file: str | None = event.get("criteria_file")
        if criteria_file:
            logger.info(
                "Loading criteria from S3",
                extra={"criteria_file": criteria_file, "request_id": request_id},
            )
            criteria = load_from_s3(criteria_file)
        else:
            criteria = DefaultCriteria.balanced()

        provider = get_provider(provider_name, config)

        logger.info(
            "Starting evaluation",
            extra={
                "provider": provider_name,
                "model": judge_model,
                "criteria_count": len(criteria.criteria),
                "request_id": request_id,
            },
        )

        result = evaluate(
            prompt=event["prompt"],
            response=event["response"],
            criteria=criteria,
            provider=provider,
            model=judge_model,
            timeout=config.request_timeout,
            provider_name=provider_name,
        )

        duration_sec = time.perf_counter() - start_time
        duration_ms = round(duration_sec * 1000)
        log_extra = {
            "provider": result["provider"],
            "model": result["judge_model"],
            "duration_ms": duration_ms,
            "request_id": request_id,
        }
        if "overall_score" in result:
            log_extra["overall_score"] = result["overall_score"]

        if duration_sec >= _DURATION_LOG_THRESHOLD_SEC:
            logger.info("Evaluation completed", extra=log_extra)
        else:
            logger.debug("Evaluation completed", extra=log_extra)

        return result

    except (ValidationError, ConfigurationError, ProviderError, CriteriaLoadError) as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000)
        logger.error(
            "Evaluation failed",
            extra={
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "request_id": request_id,
                "duration_ms": duration_ms,
            },
            exc_info=True,
        )
        raise

    except LlmJudgeError as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000)
        logger.error(
            "Evaluation failed (unknown LlmJudgeError)",
            extra={
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "request_id": request_id,
                "duration_ms": duration_ms,
            },
            exc_info=True,
        )
        raise

    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000)
        logger.critical(
            "Unexpected error in Lambda handler",
            extra={
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "request_id": request_id,
                "duration_ms": duration_ms,
            },
            exc_info=True,
        )
        raise


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _default_model(config, provider_name: str) -> str:
    """Return the default judge model for the given provider.

    Args:
        config: Loaded :class:`~src.config.Config` instance.
        provider_name: Provider identifier (``"anthropic"``, ``"openai"``,
            or ``"bedrock"``).

    Returns:
        Model name string from the matching config field.

    Raises:
        ConfigurationError: If the provider name is unrecognised.
    """
    mapping = {
        "anthropic": config.anthropic_model,
        "openai": config.openai_model,
        "bedrock": config.bedrock_model,
    }
    model = mapping.get(provider_name)
    if not model:
        raise ConfigurationError(
            f"No default model configured for provider '{provider_name}'. "
            f"Set the corresponding *_MODEL environment variable."
        )
    return model
