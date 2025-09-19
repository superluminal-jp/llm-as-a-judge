"""
Base classes for LLM providers.

Defines the common interface and base implementations for all LLM providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone
import asyncio
import logging

from ...domain.shared_kernel.value_objects import (
    ModelName,
    ProviderName,
    Score,
    Confidence,
)
from ...domain.evaluation.value_objects import (
    EvaluationPrompt,
    EvaluationResponse,
    EvaluationCriteria,
)
from ...domain.evaluation.entities import CriterionScore, MultiCriteriaResult


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMProviderResponse:
    """Standardized response from an LLM provider."""

    content: str
    usage: Dict[str, int] = field(default_factory=dict)
    model: str = "unknown"
    stop_reason: str = "stop"
    response_time_ms: float = 0.0
    provider: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate response data."""
        if not self.content or not isinstance(self.content, str):
            raise ValueError("Response content must be a non-empty string")

        if not isinstance(self.usage, dict):
            raise ValueError("Usage must be a dictionary")

        if (
            not isinstance(self.response_time_ms, (int, float))
            or self.response_time_ms < 0
        ):
            raise ValueError("Response time must be a non-negative number")


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        model: str = "unknown",
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.model = model
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "provider": self.provider,
            "model": self.model,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class RateLimitError(LLMProviderError):
    """Raised when rate limits are exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        provider: str = "unknown",
        model: str = "unknown",
        retry_after: Optional[float] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            error_code="RATE_LIMIT",
            details={"retry_after": retry_after, **kwargs},
        )
        self.retry_after = retry_after


class AuthenticationError(LLMProviderError):
    """Raised when authentication fails."""

    def __init__(
        self,
        message: str = "Authentication failed",
        provider: str = "unknown",
        model: str = "unknown",
        **kwargs,
    ):
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            error_code="AUTHENTICATION_ERROR",
            details=kwargs,
        )


class TimeoutError(LLMProviderError):
    """Raised when requests timeout."""

    def __init__(
        self,
        message: str = "Request timeout",
        provider: str = "unknown",
        model: str = "unknown",
        timeout_seconds: Optional[float] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            error_code="TIMEOUT_ERROR",
            details={"timeout_seconds": timeout_seconds, **kwargs},
        )
        self.timeout_seconds = timeout_seconds


class NetworkError(LLMProviderError):
    """Raised when network errors occur."""

    def __init__(
        self,
        message: str = "Network error",
        provider: str = "unknown",
        model: str = "unknown",
        **kwargs,
    ):
        super().__init__(
            message=message,
            provider=provider,
            model=model,
            error_code="NETWORK_ERROR",
            details=kwargs,
        )


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider_name = self._get_provider_name()
        self.logger = logging.getLogger(f"{__name__}.{self.provider_name}")
        self._is_initialized = False
        self._active_requests = 0
        self._total_requests = 0
        self._total_errors = 0

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name."""
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the provider."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the provider and cleanup resources."""
        pass

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs,
    ) -> LLMProviderResponse:
        """Generate a response from the LLM."""
        pass

    @abstractmethod
    async def evaluate_response(
        self,
        prompt: str,
        response: str,
        criteria: str = "overall quality",
        model: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Evaluate a response using the LLM."""
        pass

    @abstractmethod
    async def compare_responses(
        self,
        prompt: str,
        response_a: str,
        response_b: str,
        model: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Compare two responses using the LLM."""
        pass

    @abstractmethod
    async def evaluate_multi_criteria(
        self,
        prompt: str,
        response: str,
        criteria: EvaluationCriteria,
        model: Optional[str] = None,
        **kwargs,
    ) -> MultiCriteriaResult:
        """Perform multi-criteria evaluation."""
        pass

    @property
    def is_initialized(self) -> bool:
        """Check if provider is initialized."""
        return self._is_initialized

    @property
    def active_requests(self) -> int:
        """Get number of active requests."""
        return self._active_requests

    @property
    def total_requests(self) -> int:
        """Get total number of requests made."""
        return self._total_requests

    @property
    def total_errors(self) -> int:
        """Get total number of errors encountered."""
        return self._total_errors

    @property
    def error_rate(self) -> float:
        """Get error rate (errors / total requests)."""
        if self._total_requests == 0:
            return 0.0
        return self._total_errors / self._total_requests

    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the provider."""
        try:
            start_time = asyncio.get_event_loop().time()

            # Simple test request
            response = await self.generate_response(prompt="Hello", max_tokens=10)

            end_time = asyncio.get_event_loop().time()
            response_time = (end_time - start_time) * 1000  # Convert to ms

            return {
                "status": "healthy",
                "provider": self.provider_name,
                "response_time_ms": response_time,
                "active_requests": self._active_requests,
                "total_requests": self._total_requests,
                "total_errors": self._total_errors,
                "error_rate": self.error_rate,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "provider": self.provider_name,
                "error": str(e),
                "active_requests": self._active_requests,
                "total_requests": self._total_requests,
                "total_errors": self._total_errors,
                "error_rate": self.error_rate,
            }

    def _get_provider_name(self) -> str:
        """Get provider name from class name."""
        return self.__class__.__name__.replace("Provider", "").lower()

    def _increment_request_count(self) -> None:
        """Increment request counters."""
        self._active_requests += 1
        self._total_requests += 1

    def _decrement_request_count(self) -> None:
        """Decrement active request count."""
        self._active_requests = max(0, self._active_requests - 1)

    def _increment_error_count(self) -> None:
        """Increment error count."""
        self._total_errors += 1

    async def _execute_with_metrics(
        self, operation: callable, operation_name: str, **kwargs
    ) -> Any:
        """Execute an operation with metrics tracking."""
        self._increment_request_count()
        start_time = asyncio.get_event_loop().time()

        try:
            self.logger.debug(f"Starting {operation_name} with {self.provider_name}")
            result = await operation(**kwargs)

            end_time = asyncio.get_event_loop().time()
            duration_ms = (end_time - start_time) * 1000

            self.logger.debug(f"Completed {operation_name} in {duration_ms:.2f}ms")
            return result

        except Exception as e:
            self._increment_error_count()
            self.logger.error(f"Error in {operation_name}: {e}")
            raise
        finally:
            self._decrement_request_count()

    def get_metrics(self) -> Dict[str, Any]:
        """Get provider metrics."""
        return {
            "provider": self.provider_name,
            "is_initialized": self._is_initialized,
            "active_requests": self._active_requests,
            "total_requests": self._total_requests,
            "total_errors": self._total_errors,
            "error_rate": self.error_rate,
        }
