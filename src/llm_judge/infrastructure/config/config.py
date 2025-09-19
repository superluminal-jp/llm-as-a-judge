"""Configuration management for LLM-as-a-Judge system."""

import os
import logging
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

try:
    from dotenv import load_dotenv

    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    logging.warning(
        "python-dotenv not installed. Environment variables must be set manually."
    )


@dataclass
class LLMConfig:
    """Configuration for LLM providers."""

    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    aws_region: str = "us-east-1"
    default_provider: str = "openai"
    openai_model: str = "gpt-5-2025-08-07"
    anthropic_model: str = "claude-sonnet-4-20250514"
    bedrock_model: str = "amazon.nova-premier-v1:0"
    gpt5_reasoning_effort: str = "medium"
    anthropic_temperature: Optional[float] = 0.1
    anthropic_top_p: Optional[float] = None
    bedrock_temperature: Optional[float] = 0.1
    request_timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 1
    log_level: str = "INFO"
    default_criteria_type: str = "comprehensive"

    # Criteria weight configuration
    criteria_weights: Optional[str] = (
        None  # Format: "criterion1:weight1,criterion2:weight2"
    )
    use_equal_weights: bool = True  # Default to equal weights

    # Custom criteria configuration
    custom_criteria: Optional[str] = (
        None  # Format: "name:description:type:weight,name2:description2:type2:weight2"
    )
    criteria_file: Optional[str] = None  # Path to JSON file containing custom criteria

    # Data persistence configuration
    persistence_enabled: bool = True
    persistence_storage_path: str = "./data"
    persistence_cache_enabled: bool = True
    persistence_cache_ttl_hours: int = 24
    persistence_max_cache_size: int = 1000
    persistence_auto_cleanup: bool = True

    # Provider-specific timeout configuration
    openai_request_timeout: int = 30
    anthropic_request_timeout: int = 30
    bedrock_request_timeout: int = 30
    openai_connect_timeout: int = 10
    anthropic_connect_timeout: int = 10
    bedrock_connect_timeout: int = 10

    # Enhanced retry configuration
    retry_max_attempts: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    retry_backoff_multiplier: float = 2.0
    retry_jitter_enabled: bool = True

    # Circuit breaker configuration
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 60.0
    circuit_breaker_success_threshold: int = 2

    def __post_init__(self):
        """Validate configuration after initialization."""
        # Skip validation if this is for testing
        if not getattr(self, "_skip_validation", False):
            self._validate_config()

    def _validate_config(self):
        """Validate configuration values and provide helpful error messages."""
        errors = []

        # Validate provider configuration
        if (
            not self.openai_api_key
            and not self.anthropic_api_key
            and not self.aws_access_key_id
        ):
            errors.append(
                "No API keys configured. Please set OPENAI_API_KEY, ANTHROPIC_API_KEY, or AWS credentials "
                "in your environment or .env file."
            )

        # Validate default provider
        if self.default_provider not in ["openai", "anthropic", "bedrock"]:
            errors.append(
                f"Invalid default_provider '{self.default_provider}'. Must be 'openai', 'anthropic', or 'bedrock'."
            )

        # Validate provider-specific keys
        if self.default_provider == "openai" and not self.openai_api_key:
            errors.append(
                "DEFAULT_PROVIDER is set to 'openai' but OPENAI_API_KEY is not configured. "
                "Please set OPENAI_API_KEY in your environment or .env file."
            )

        if self.default_provider == "anthropic" and not self.anthropic_api_key:
            errors.append(
                "DEFAULT_PROVIDER is set to 'anthropic' but ANTHROPIC_API_KEY is not configured. "
                "Please set ANTHROPIC_API_KEY in your environment or .env file."
            )

        if self.default_provider == "bedrock" and (
            not self.aws_access_key_id or not self.aws_secret_access_key
        ):
            errors.append(
                "DEFAULT_PROVIDER is set to 'bedrock' but AWS credentials are not configured. "
                "Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in your environment or .env file."
            )

        # Validate numeric values
        if self.request_timeout <= 0:
            errors.append(
                f"request_timeout must be positive, got {self.request_timeout}"
            )

        if self.openai_request_timeout <= 0:
            errors.append(
                f"openai_request_timeout must be positive, got {self.openai_request_timeout}"
            )

        if self.anthropic_request_timeout <= 0:
            errors.append(
                f"anthropic_request_timeout must be positive, got {self.anthropic_request_timeout}"
            )

        if self.bedrock_request_timeout <= 0:
            errors.append(
                f"bedrock_request_timeout must be positive, got {self.bedrock_request_timeout}"
            )

        if self.openai_connect_timeout <= 0:
            errors.append(
                f"openai_connect_timeout must be positive, got {self.openai_connect_timeout}"
            )

        if self.anthropic_connect_timeout <= 0:
            errors.append(
                f"anthropic_connect_timeout must be positive, got {self.anthropic_connect_timeout}"
            )

        if self.bedrock_connect_timeout <= 0:
            errors.append(
                f"bedrock_connect_timeout must be positive, got {self.bedrock_connect_timeout}"
            )

        if self.max_retries < 0:
            errors.append(f"max_retries must be non-negative, got {self.max_retries}")

        if self.retry_delay < 0:
            errors.append(f"retry_delay must be non-negative, got {self.retry_delay}")

        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_log_levels:
            errors.append(
                f"Invalid log_level '{self.log_level}'. Must be one of: {valid_log_levels}"
            )

        # Validate GPT-5 reasoning effort
        valid_reasoning_efforts = ["low", "medium", "high"]
        if self.gpt5_reasoning_effort not in valid_reasoning_efforts:
            errors.append(
                f"Invalid gpt5_reasoning_effort '{self.gpt5_reasoning_effort}'. Must be one of: {valid_reasoning_efforts}"
            )

        # Validate default criteria type
        valid_criteria_types = ["comprehensive", "basic", "technical", "creative"]
        if self.default_criteria_type not in valid_criteria_types:
            errors.append(
                f"Invalid default_criteria_type '{self.default_criteria_type}'. Must be one of: {valid_criteria_types}"
            )

        # Validate Anthropic temperature and top_p
        if self.anthropic_temperature is not None and (
            self.anthropic_temperature < 0 or self.anthropic_temperature > 1
        ):
            errors.append(
                f"anthropic_temperature must be between 0 and 1, got {self.anthropic_temperature}"
            )

        if self.anthropic_top_p is not None and (
            self.anthropic_top_p < 0 or self.anthropic_top_p > 1
        ):
            errors.append(
                f"anthropic_top_p must be between 0 and 1, got {self.anthropic_top_p}"
            )

        # Validate Bedrock temperature
        if self.bedrock_temperature is not None and (
            self.bedrock_temperature < 0 or self.bedrock_temperature > 1
        ):
            errors.append(
                f"bedrock_temperature must be between 0 and 1, got {self.bedrock_temperature}"
            )

        # Warn if both temperature and top_p are specified (they're mutually exclusive)
        if self.anthropic_temperature is not None and self.anthropic_top_p is not None:
            errors.append(
                "Both anthropic_temperature and anthropic_top_p are specified. Use only one (they are mutually exclusive)."
            )

        # Validate retry configuration
        if self.retry_max_attempts <= 0:
            errors.append(
                f"retry_max_attempts must be positive, got {self.retry_max_attempts}"
            )

        if self.retry_base_delay < 0:
            errors.append(
                f"retry_base_delay must be non-negative, got {self.retry_base_delay}"
            )

        if self.retry_max_delay < self.retry_base_delay:
            errors.append(
                f"retry_max_delay ({self.retry_max_delay}) must be >= retry_base_delay ({self.retry_base_delay})"
            )

        if self.retry_backoff_multiplier <= 1.0:
            errors.append(
                f"retry_backoff_multiplier must be > 1.0, got {self.retry_backoff_multiplier}"
            )

        # Validate circuit breaker configuration
        if self.circuit_breaker_failure_threshold <= 0:
            errors.append(
                f"circuit_breaker_failure_threshold must be positive, got {self.circuit_breaker_failure_threshold}"
            )

        if self.circuit_breaker_recovery_timeout <= 0:
            errors.append(
                f"circuit_breaker_recovery_timeout must be positive, got {self.circuit_breaker_recovery_timeout}"
            )

        if self.circuit_breaker_success_threshold <= 0:
            errors.append(
                f"circuit_breaker_success_threshold must be positive, got {self.circuit_breaker_success_threshold}"
            )

        if errors:
            error_message = "Configuration validation failed:\n" + "\n".join(
                f"  - {error}" for error in errors
            )
            error_message += "\n\nPlease check your .env file or environment variables."
            raise ValueError(error_message)


def load_config() -> LLMConfig:
    """Load configuration from environment variables and .env file."""

    # Load .env file if available
    if DOTENV_AVAILABLE:
        env_path = Path(".env")
        if env_path.exists():
            load_dotenv(env_path)
            logging.info(f"Loaded configuration from {env_path}")
        else:
            logging.info("No .env file found, using environment variables only")

    # Load configuration from environment
    try:
        # Handle optional float parameters
        anthropic_temperature = None
        if os.getenv("ANTHROPIC_TEMPERATURE"):
            anthropic_temperature = float(os.getenv("ANTHROPIC_TEMPERATURE"))

        anthropic_top_p = None
        if os.getenv("ANTHROPIC_TOP_P"):
            anthropic_top_p = float(os.getenv("ANTHROPIC_TOP_P"))

        # Handle optional Bedrock temperature
        bedrock_temperature = None
        if os.getenv("BEDROCK_TEMPERATURE"):
            bedrock_temperature = float(os.getenv("BEDROCK_TEMPERATURE"))

        config = LLMConfig(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN"),  # Optional
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            default_provider=os.getenv("DEFAULT_PROVIDER", "openai"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5-2025-08-07"),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            bedrock_model=os.getenv("BEDROCK_MODEL", "amazon.nova-premier-v1:0"),
            gpt5_reasoning_effort=os.getenv("GPT5_REASONING_EFFORT", "medium"),
            anthropic_temperature=anthropic_temperature,
            anthropic_top_p=anthropic_top_p,
            bedrock_temperature=bedrock_temperature,
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "30")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            retry_delay=int(os.getenv("RETRY_DELAY", "1")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            default_criteria_type=os.getenv("DEFAULT_CRITERIA_TYPE", "comprehensive"),
            # Enhanced retry configuration
            retry_max_attempts=int(os.getenv("RETRY_MAX_ATTEMPTS", "3")),
            retry_base_delay=float(os.getenv("RETRY_BASE_DELAY", "1.0")),
            retry_max_delay=float(os.getenv("RETRY_MAX_DELAY", "60.0")),
            retry_backoff_multiplier=float(
                os.getenv("RETRY_BACKOFF_MULTIPLIER", "2.0")
            ),
            retry_jitter_enabled=os.getenv("RETRY_JITTER_ENABLED", "true").lower()
            == "true",
            # Provider-specific timeout configuration
            openai_request_timeout=int(
                os.getenv("OPENAI_REQUEST_TIMEOUT", os.getenv("REQUEST_TIMEOUT", "30"))
            ),
            anthropic_request_timeout=int(
                os.getenv(
                    "ANTHROPIC_REQUEST_TIMEOUT", os.getenv("REQUEST_TIMEOUT", "30")
                )
            ),
            bedrock_request_timeout=int(
                os.getenv("BEDROCK_REQUEST_TIMEOUT", os.getenv("REQUEST_TIMEOUT", "30"))
            ),
            openai_connect_timeout=int(os.getenv("OPENAI_CONNECT_TIMEOUT", "10")),
            anthropic_connect_timeout=int(os.getenv("ANTHROPIC_CONNECT_TIMEOUT", "10")),
            bedrock_connect_timeout=int(os.getenv("BEDROCK_CONNECT_TIMEOUT", "10")),
            # Circuit breaker configuration
            circuit_breaker_enabled=os.getenv("CIRCUIT_BREAKER_ENABLED", "true").lower()
            == "true",
            circuit_breaker_failure_threshold=int(
                os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")
            ),
            circuit_breaker_recovery_timeout=float(
                os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "60.0")
            ),
            circuit_breaker_success_threshold=int(
                os.getenv("CIRCUIT_BREAKER_SUCCESS_THRESHOLD", "2")
            ),
        )

        logging.info("Configuration loaded successfully")
        return config

    except ValueError as e:
        logging.error(f"Configuration error: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error loading configuration: {e}")
        raise ValueError(f"Failed to load configuration: {e}")


def setup_logging(config: LLMConfig):
    """Setup enhanced logging based on configuration."""
    try:
        from logging_config import setup_enhanced_logging

        return setup_enhanced_logging(config)
    except ImportError:
        # Fallback to basic logging if enhanced logging is not available
        logging.basicConfig(
            level=getattr(logging, config.log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Ensure sensitive information is never logged
        logging.getLogger().addFilter(_sanitize_log_filter)
        return logging.getLogger("llm_judge")


def _sanitize_log_filter(record):
    """Filter to prevent API keys from being logged."""
    if hasattr(record, "msg") and isinstance(record.msg, str):
        # Redact common API key patterns
        msg = record.msg
        for key_name in ["api_key", "token", "key", "secret"]:
            if key_name in msg.lower():
                record.msg = msg.replace(
                    record.msg, "[REDACTED - API key detected in log message]"
                )
                break
    return True
