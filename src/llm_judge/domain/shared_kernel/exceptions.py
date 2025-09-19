"""
Domain Exceptions for the Shared Kernel.

Domain-specific exceptions that represent business rule violations
and domain errors.
"""

from typing import Any, Dict, Optional


class DomainException(Exception):
    """Base exception for all domain-related errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class InvalidScoreException(DomainException):
    """Raised when a score is invalid."""

    def __init__(self, score: Any, min_value: float = 1.0, max_value: float = 5.0):
        message = (
            f"Invalid score: {score}. Score must be between {min_value} and {max_value}"
        )
        super().__init__(
            message=message,
            error_code="INVALID_SCORE",
            details={"score": score, "min_value": min_value, "max_value": max_value},
        )


class InvalidModelException(DomainException):
    """Raised when a model name is invalid."""

    def __init__(self, model: str, valid_models: Optional[list] = None):
        message = f"Invalid model: {model}"
        if valid_models:
            message += f". Valid models: {', '.join(valid_models)}"

        super().__init__(
            message=message,
            error_code="INVALID_MODEL",
            details={"model": model, "valid_models": valid_models},
        )


class InvalidProviderException(DomainException):
    """Raised when a provider is invalid."""

    def __init__(self, provider: str, valid_providers: Optional[list] = None):
        message = f"Invalid provider: {provider}"
        if valid_providers:
            message += f". Valid providers: {', '.join(valid_providers)}"

        super().__init__(
            message=message,
            error_code="INVALID_PROVIDER",
            details={"provider": provider, "valid_providers": valid_providers},
        )


class EvaluationException(DomainException):
    """Base exception for evaluation-related errors."""

    def __init__(
        self,
        message: str,
        evaluation_id: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="EVALUATION_ERROR",
            details={
                "evaluation_id": evaluation_id,
                "provider": provider,
                "model": model,
                **kwargs,
            },
        )


class EvaluationTimeoutException(EvaluationException):
    """Raised when an evaluation times out."""

    def __init__(
        self,
        timeout_seconds: float,
        evaluation_id: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        message = f"Evaluation timed out after {timeout_seconds} seconds"
        super().__init__(
            message=message,
            error_code="EVALUATION_TIMEOUT",
            evaluation_id=evaluation_id,
            provider=provider,
            model=model,
            timeout_seconds=timeout_seconds,
        )


class EvaluationRateLimitException(EvaluationException):
    """Raised when evaluation hits rate limits."""

    def __init__(
        self,
        retry_after: Optional[float] = None,
        evaluation_id: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        message = "Evaluation rate limit exceeded"
        if retry_after:
            message += f". Retry after {retry_after} seconds"

        super().__init__(
            message=message,
            error_code="EVALUATION_RATE_LIMIT",
            evaluation_id=evaluation_id,
            provider=provider,
            model=model,
            retry_after=retry_after,
        )


class EvaluationAuthenticationException(EvaluationException):
    """Raised when evaluation fails due to authentication issues."""

    def __init__(
        self,
        provider: str,
        evaluation_id: Optional[str] = None,
        model: Optional[str] = None,
    ):
        message = f"Authentication failed for provider: {provider}"
        super().__init__(
            message=message,
            error_code="EVALUATION_AUTH_ERROR",
            evaluation_id=evaluation_id,
            provider=provider,
            model=model,
        )


class BatchProcessingException(DomainException):
    """Base exception for batch processing errors."""

    def __init__(self, message: str, batch_id: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="BATCH_PROCESSING_ERROR",
            details={"batch_id": batch_id, **kwargs},
        )


class BatchValidationException(BatchProcessingException):
    """Raised when batch validation fails."""

    def __init__(self, validation_errors: list, batch_id: Optional[str] = None):
        message = f"Batch validation failed: {', '.join(validation_errors)}"
        super().__init__(
            message=message,
            error_code="BATCH_VALIDATION_ERROR",
            batch_id=batch_id,
            validation_errors=validation_errors,
        )


class BatchProcessingTimeoutException(BatchProcessingException):
    """Raised when batch processing times out."""

    def __init__(
        self,
        timeout_seconds: float,
        items_processed: int,
        total_items: int,
        batch_id: Optional[str] = None,
    ):
        message = f"Batch processing timed out after {timeout_seconds} seconds. Processed {items_processed}/{total_items} items"
        super().__init__(
            message=message,
            error_code="BATCH_PROCESSING_TIMEOUT",
            batch_id=batch_id,
            timeout_seconds=timeout_seconds,
            items_processed=items_processed,
            total_items=total_items,
        )


class CriteriaException(DomainException):
    """Base exception for criteria-related errors."""

    def __init__(self, message: str, criteria_name: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="CRITERIA_ERROR",
            details={"criteria_name": criteria_name, **kwargs},
        )


class InvalidCriteriaException(CriteriaException):
    """Raised when criteria configuration is invalid."""

    def __init__(self, criteria_name: str, validation_errors: list):
        message = f"Invalid criteria '{criteria_name}': {', '.join(validation_errors)}"
        super().__init__(
            message=message,
            error_code="INVALID_CRITERIA",
            criteria_name=criteria_name,
            validation_errors=validation_errors,
        )


class CriteriaWeightException(CriteriaException):
    """Raised when criteria weights are invalid."""

    def __init__(self, message: str, weights: Optional[Dict[str, float]] = None):
        super().__init__(
            message=message, error_code="CRITERIA_WEIGHT_ERROR", weights=weights
        )


class PersistenceException(DomainException):
    """Base exception for persistence-related errors."""

    def __init__(self, message: str, operation: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code="PERSISTENCE_ERROR",
            details={"operation": operation, **kwargs},
        )


class CacheException(PersistenceException):
    """Raised when cache operations fail."""

    def __init__(
        self,
        message: str,
        cache_key: Optional[str] = None,
        operation: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            error_code="CACHE_ERROR",
            operation=operation,
            cache_key=cache_key,
        )


class StorageException(PersistenceException):
    """Raised when storage operations fail."""

    def __init__(
        self,
        message: str,
        storage_path: Optional[str] = None,
        operation: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            error_code="STORAGE_ERROR",
            operation=operation,
            storage_path=storage_path,
        )
