"""Enhanced retry strategies with exponential backoff, jitter, and circuit breaker patterns."""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, List, Type
from enum import Enum

from ..config.config import LLMConfig
from .error_classification import get_error_classifier, get_error_handler, ErrorCategory


class ErrorType(Enum):
    """Classification of error types for retry policies."""
    TRANSIENT = "transient"       # Network errors, temporary server issues
    RATE_LIMIT = "rate_limit"     # API rate limiting
    AUTHENTICATION = "auth"       # Authentication failures (usually permanent)
    CLIENT_ERROR = "client"       # 4xx errors (usually permanent)
    SERVER_ERROR = "server"       # 5xx errors (usually transient)
    TIMEOUT = "timeout"           # Request timeouts
    UNKNOWN = "unknown"           # Unknown errors


@dataclass
class RetryPolicy:
    """Configuration for retry behavior per error type."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter_enabled: bool = True
    enabled: bool = True


@dataclass
class CircuitBreakerState:
    """State tracking for circuit breaker pattern."""
    failure_count: int = 0
    last_failure_time: Optional[float] = None
    state: str = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # seconds
    success_threshold: int = 2  # successes needed to close circuit


class EnhancedRetryManager:
    """Advanced retry manager with exponential backoff, jitter, and circuit breaker."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        try:
            from logging_config import get_logger
            self.logger = get_logger(__name__)
        except ImportError:
            self.logger = logging.getLogger(__name__)
        
        # Initialize error classification system
        self.error_classifier = get_error_classifier()
        self.error_handler = get_error_handler()
        
        # Circuit breaker states per service
        self.circuit_breakers: Dict[str, CircuitBreakerState] = {}
        
        # Create retry policies from configuration
        base_policy = RetryPolicy(
            max_attempts=config.retry_max_attempts,
            base_delay=config.retry_base_delay,
            max_delay=config.retry_max_delay,
            backoff_multiplier=config.retry_backoff_multiplier,
            jitter_enabled=config.retry_jitter_enabled
        )
        
        # Retry policies per error type (can be customized per error type)
        self.retry_policies = {
            ErrorType.TRANSIENT: RetryPolicy(**base_policy.__dict__),
            ErrorType.RATE_LIMIT: RetryPolicy(
                max_attempts=max(config.retry_max_attempts, 5),  # More retries for rate limits
                base_delay=config.retry_base_delay * 2,  # Longer delays
                max_delay=min(config.retry_max_delay * 2, 300.0),  # Cap at 5 minutes
                backoff_multiplier=config.retry_backoff_multiplier,
                jitter_enabled=config.retry_jitter_enabled
            ),
            ErrorType.SERVER_ERROR: RetryPolicy(**base_policy.__dict__),
            ErrorType.TIMEOUT: RetryPolicy(
                max_attempts=max(config.retry_max_attempts - 1, 2),  # Fewer retries for timeouts
                base_delay=config.retry_base_delay * 0.5,  # Shorter delays
                max_delay=min(config.retry_max_delay, 30.0),  # Cap at 30 seconds
                backoff_multiplier=config.retry_backoff_multiplier,
                jitter_enabled=config.retry_jitter_enabled
            ),
            ErrorType.AUTHENTICATION: RetryPolicy(enabled=False),  # Don't retry auth errors
            ErrorType.CLIENT_ERROR: RetryPolicy(enabled=False),   # Don't retry 4xx errors
            ErrorType.UNKNOWN: RetryPolicy(
                max_attempts=max(config.retry_max_attempts - 1, 2),
                base_delay=config.retry_base_delay,
                max_delay=config.retry_max_delay,
                backoff_multiplier=config.retry_backoff_multiplier,
                jitter_enabled=config.retry_jitter_enabled
            )
        }
        
        # Override circuit breaker defaults with configuration
        CircuitBreakerState.failure_threshold = config.circuit_breaker_failure_threshold
        CircuitBreakerState.recovery_timeout = config.circuit_breaker_recovery_timeout
        CircuitBreakerState.success_threshold = config.circuit_breaker_success_threshold
        
        self.logger.info("Enhanced retry manager initialized")
    
    def classify_error(self, exception: Exception) -> ErrorType:
        """Classify an exception using comprehensive error classification system."""
        # Use the comprehensive error classification system
        classification = self.error_classifier.classify_error(exception)
        
        # Map comprehensive categories to existing ErrorType enum
        category_mapping = {
            ErrorCategory.TRANSIENT: ErrorType.TRANSIENT,
            ErrorCategory.RATE_LIMIT: ErrorType.RATE_LIMIT,
            ErrorCategory.AUTHENTICATION: ErrorType.AUTHENTICATION,
            ErrorCategory.USER: ErrorType.CLIENT_ERROR,
            ErrorCategory.SYSTEM: ErrorType.SERVER_ERROR,
            ErrorCategory.NETWORK: ErrorType.TRANSIENT,
            ErrorCategory.TIMEOUT: ErrorType.TIMEOUT,
            ErrorCategory.PERMANENT: ErrorType.CLIENT_ERROR  # Treat permanent errors as client errors for retry logic
        }
        
        return category_mapping.get(classification.category, ErrorType.UNKNOWN)
    
    def get_circuit_breaker(self, service_name: str) -> CircuitBreakerState:
        """Get or create circuit breaker state for a service."""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreakerState()
        return self.circuit_breakers[service_name]
    
    def check_circuit_breaker(self, service_name: str) -> bool:
        """Check if circuit breaker allows request. Returns True if request should proceed."""
        cb = self.get_circuit_breaker(service_name)
        current_time = time.time()
        
        if cb.state == "CLOSED":
            return True
        elif cb.state == "OPEN":
            # Check if we should transition to HALF_OPEN
            if (cb.last_failure_time and 
                current_time - cb.last_failure_time >= cb.recovery_timeout):
                cb.state = "HALF_OPEN"
                self.logger.info(f"Circuit breaker for {service_name} transitioning to HALF_OPEN")
                return True
            return False
        elif cb.state == "HALF_OPEN":
            return True
        
        return False
    
    def record_success(self, service_name: str):
        """Record a successful operation for circuit breaker."""
        cb = self.get_circuit_breaker(service_name)
        
        if cb.state == "HALF_OPEN":
            cb.failure_count = 0
            cb.state = "CLOSED"
            if hasattr(self.logger, 'log_circuit_breaker'):
                self.logger.log_circuit_breaker(service_name, "CLOSED", cb.failure_count)
            else:
                self.logger.info(f"Circuit breaker for {service_name} closed after successful recovery")
        elif cb.state == "CLOSED":
            cb.failure_count = max(0, cb.failure_count - 1)  # Gradually reduce failure count
    
    def record_failure(self, service_name: str, error_type: ErrorType):
        """Record a failed operation for circuit breaker."""
        cb = self.get_circuit_breaker(service_name)
        cb.failure_count += 1
        cb.last_failure_time = time.time()
        
        # Only open circuit for certain error types
        if error_type in [ErrorType.SERVER_ERROR, ErrorType.TIMEOUT, ErrorType.TRANSIENT]:
            if cb.failure_count >= cb.failure_threshold:
                if cb.state != "OPEN":
                    cb.state = "OPEN"
                    if hasattr(self.logger, 'log_circuit_breaker'):
                        self.logger.log_circuit_breaker(service_name, "OPEN", cb.failure_count)
                    else:
                        self.logger.warning(f"Circuit breaker for {service_name} opened after {cb.failure_count} failures")
        
        # Rate limits don't trigger circuit breaker, just record the failure
        if error_type == ErrorType.RATE_LIMIT:
            cb.failure_count = max(0, cb.failure_count - 1)  # Don't count rate limits as failures
    
    def calculate_delay(self, attempt: int, error_type: ErrorType, base_delay: Optional[float] = None) -> float:
        """Calculate delay with exponential backoff and jitter."""
        policy = self.retry_policies.get(error_type, self.retry_policies[ErrorType.UNKNOWN])
        
        if base_delay is None:
            base_delay = policy.base_delay
        
        # Exponential backoff
        delay = base_delay * (policy.backoff_multiplier ** (attempt - 1))
        
        # Cap at max delay
        delay = min(delay, policy.max_delay)
        
        # Add jitter if enabled
        if policy.jitter_enabled:
            # Full jitter: delay = random(0, delay)
            delay = random.uniform(0, delay)
        
        return delay
    
    async def execute_with_retry(
        self,
        operation: Callable,
        service_name: str,
        operation_name: str = "unknown",
        *args,
        **kwargs
    ) -> Any:
        """Execute an operation with retry logic and circuit breaker protection."""
        
        # Check circuit breaker first
        if not self.check_circuit_breaker(service_name):
            raise Exception(f"Circuit breaker is OPEN for {service_name}")
        
        last_exception = None
        
        for attempt in range(1, max(policy.max_attempts for policy in self.retry_policies.values()) + 1):
            try:
                self.logger.debug(f"Attempt {attempt} for {service_name}.{operation_name}")
                result = await operation(*args, **kwargs)
                
                # Record success for circuit breaker
                self.record_success(service_name)
                
                if attempt > 1:
                    self.logger.info(f"Operation {service_name}.{operation_name} succeeded on attempt {attempt}")
                
                return result
                
            except Exception as e:
                last_exception = e
                error_type = self.classify_error(e)
                policy = self.retry_policies.get(error_type, self.retry_policies[ErrorType.UNKNOWN])
                
                # Use error classification system for comprehensive error handling
                context = {
                    "service_name": service_name,
                    "operation_name": operation_name,
                    "attempt": attempt,
                    "max_attempts": policy.max_attempts
                }
                
                # Get correlation ID if available
                correlation_id = getattr(self.logger, '_correlation_id', None) if hasattr(self.logger, '_correlation_id') else None
                
                # Handle error with classification system (async)
                should_retry, user_message = await self.error_handler.handle_error(e, context, correlation_id)
                
                # Record failure for circuit breaker
                self.record_failure(service_name, error_type)
                
                # Check if we should retry
                if not policy.enabled or attempt >= policy.max_attempts:
                    self.logger.error(f"Operation {service_name}.{operation_name} failed permanently after {attempt} attempts: {e}")
                    break
                
                # Calculate delay and wait
                delay = self.calculate_delay(attempt, error_type)
                if hasattr(self.logger, 'log_retry_attempt'):
                    self.logger.log_retry_attempt(attempt, policy.max_attempts, str(e), delay, 
                                                service=service_name, operation=operation_name, 
                                                error_type=error_type.value)
                else:
                    self.logger.warning(f"Attempt {attempt} failed for {service_name}.{operation_name}: {e}. Retrying in {delay:.2f}s")
                
                await asyncio.sleep(delay)
        
        # All retries exhausted
        self.logger.error(f"All retry attempts exhausted for {service_name}.{operation_name}")
        raise last_exception
    
    def get_retry_stats(self) -> Dict[str, Any]:
        """Get current retry and circuit breaker statistics."""
        stats = {
            "circuit_breakers": {}
        }
        
        for service_name, cb in self.circuit_breakers.items():
            stats["circuit_breakers"][service_name] = {
                "state": cb.state,
                "failure_count": cb.failure_count,
                "last_failure_time": cb.last_failure_time,
                "time_since_last_failure": time.time() - cb.last_failure_time if cb.last_failure_time else None
            }
        
        return stats


# Decorator for easy retry application
def with_enhanced_retry(service_name: str, operation_name: str = None):
    """Decorator to apply enhanced retry logic to async functions."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get retry manager from first argument (should be client instance)
            retry_manager = getattr(args[0], '_retry_manager', None)
            if not retry_manager:
                # Fallback to direct execution if no retry manager
                return await func(*args, **kwargs)
            
            op_name = operation_name or func.__name__
            return await retry_manager.execute_with_retry(
                func, service_name, op_name, *args, **kwargs
            )
        return wrapper
    return decorator