"""Error classification system for LLM-as-a-Judge with appropriate handling strategies."""

import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import re

try:
    from logging_config import get_logger
except ImportError:
    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)


class ErrorCategory(Enum):
    """Categories of errors for classification."""
    TRANSIENT = "transient"      # Temporary errors that may resolve with retry
    PERMANENT = "permanent"      # Errors that won't resolve with retry
    USER = "user"               # User input or configuration errors
    SYSTEM = "system"           # System-level errors (infrastructure, etc.)
    RATE_LIMIT = "rate_limit"   # Rate limiting errors
    AUTHENTICATION = "authentication"  # Authentication/authorization errors
    TIMEOUT = "timeout"         # Timeout-related errors
    NETWORK = "network"         # Network connectivity errors


class ErrorSeverity(Enum):
    """Severity levels for errors."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorClassification:
    """Classification result for an error."""
    category: ErrorCategory
    severity: ErrorSeverity
    is_retryable: bool
    suggested_action: str
    user_message: str
    technical_details: Dict[str, Any]
    correlation_id: Optional[str] = None


@dataclass
class ErrorHandlingStrategy:
    """Strategy for handling a specific error category."""
    max_retries: int
    base_delay: float
    backoff_multiplier: float
    should_alert: bool
    should_fallback: bool
    user_visible: bool


class ErrorClassifier:
    """Classifies errors and determines appropriate handling strategies."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Error patterns for classification
        self.error_patterns = {
            # Authentication errors
            ErrorCategory.AUTHENTICATION: [
                r'authentication.*failed',
                r'invalid.*api.*key',
                r'unauthorized',
                r'forbidden',
                r'401',
                r'403'
            ],
            
            # Rate limiting errors
            ErrorCategory.RATE_LIMIT: [
                r'rate.*limit',
                r'quota.*exceeded',
                r'too.*many.*requests',
                r'429',
                r'throttle'
            ],
            
            # Network errors
            ErrorCategory.NETWORK: [
                r'connection.*failed',
                r'network.*error',
                r'dns.*resolution',
                r'host.*unreachable',
                r'connection.*timeout',
                r'socket.*error'
            ],
            
            # Timeout errors
            ErrorCategory.TIMEOUT: [
                r'timeout',
                r'timed.*out',
                r'deadline.*exceeded',
                r'request.*timeout'
            ],
            
            # User input errors
            ErrorCategory.USER: [
                r'invalid.*input',
                r'validation.*failed',
                r'bad.*request',
                r'malformed.*request',
                r'400'
            ],
            
            # System errors
            ErrorCategory.SYSTEM: [
                r'internal.*server.*error',
                r'service.*unavailable',
                r'500',
                r'502',
                r'503',
                r'504'
            ]
        }
        
        # Default handling strategies per category
        self.handling_strategies = {
            ErrorCategory.TRANSIENT: ErrorHandlingStrategy(
                max_retries=3,
                base_delay=1.0,
                backoff_multiplier=2.0,
                should_alert=False,
                should_fallback=True,
                user_visible=False
            ),
            ErrorCategory.PERMANENT: ErrorHandlingStrategy(
                max_retries=0,
                base_delay=0.0,
                backoff_multiplier=1.0,
                should_alert=True,
                should_fallback=True,
                user_visible=True
            ),
            ErrorCategory.USER: ErrorHandlingStrategy(
                max_retries=0,
                base_delay=0.0,
                backoff_multiplier=1.0,
                should_alert=False,
                should_fallback=False,
                user_visible=True
            ),
            ErrorCategory.SYSTEM: ErrorHandlingStrategy(
                max_retries=2,
                base_delay=2.0,
                backoff_multiplier=2.0,
                should_alert=True,
                should_fallback=True,
                user_visible=False
            ),
            ErrorCategory.RATE_LIMIT: ErrorHandlingStrategy(
                max_retries=5,
                base_delay=10.0,
                backoff_multiplier=2.0,
                should_alert=False,
                should_fallback=True,
                user_visible=False
            ),
            ErrorCategory.AUTHENTICATION: ErrorHandlingStrategy(
                max_retries=0,
                base_delay=0.0,
                backoff_multiplier=1.0,
                should_alert=True,
                should_fallback=False,
                user_visible=True
            ),
            ErrorCategory.TIMEOUT: ErrorHandlingStrategy(
                max_retries=3,
                base_delay=1.0,
                backoff_multiplier=1.5,
                should_alert=False,
                should_fallback=True,
                user_visible=False
            ),
            ErrorCategory.NETWORK: ErrorHandlingStrategy(
                max_retries=3,
                base_delay=2.0,
                backoff_multiplier=2.0,
                should_alert=False,
                should_fallback=True,
                user_visible=False
            )
        }
        
        self.logger.info("Error classifier initialized with comprehensive categorization")
    
    def classify_error(
        self, 
        error: Exception, 
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> ErrorClassification:
        """Classify an error and determine appropriate handling strategy."""
        error_text = str(error).lower()
        error_type = type(error).__name__
        
        # Add context information
        if context is None:
            context = {}
        
        technical_details = {
            "error_type": error_type,
            "error_message": str(error),
            "context": context,
            "timestamp": time.time()
        }
        
        # Classify the error
        category = self._determine_category(error, error_text, error_type)
        severity = self._determine_severity(category, error, context)
        strategy = self.handling_strategies.get(category, self.handling_strategies[ErrorCategory.SYSTEM])
        
        # Generate user-friendly messages
        user_message = self._generate_user_message(category, error, context)
        suggested_action = self._generate_suggested_action(category, error, context)
        
        classification = ErrorClassification(
            category=category,
            severity=severity,
            is_retryable=strategy.max_retries > 0,
            suggested_action=suggested_action,
            user_message=user_message,
            technical_details=technical_details,
            correlation_id=correlation_id
        )
        
        # Log the classification
        self._log_classification(classification)
        
        return classification
    
    def _determine_category(self, error: Exception, error_text: str, error_type: str) -> ErrorCategory:
        """Determine the error category based on error details."""
        
        # Check specific exception types first
        if 'TimeoutError' in error_type or 'asyncio.TimeoutError' in error_type:
            return ErrorCategory.TIMEOUT
        
        if 'ConnectionError' in error_type or 'ConnectTimeout' in error_type:
            return ErrorCategory.NETWORK
        
        # Check patterns in error message
        for category, patterns in self.error_patterns.items():
            for pattern in patterns:
                if re.search(pattern, error_text, re.IGNORECASE):
                    return category
        
        # Check for HTTP status codes in error message
        status_code_match = re.search(r'\b(\d{3})\b', error_text)
        if status_code_match:
            status_code = int(status_code_match.group(1))
            if status_code == 401 or status_code == 403:
                return ErrorCategory.AUTHENTICATION
            elif status_code == 429:
                return ErrorCategory.RATE_LIMIT
            elif status_code >= 400 and status_code < 500:
                return ErrorCategory.USER
            elif status_code >= 500:
                return ErrorCategory.SYSTEM
        
        # Default classification
        if any(keyword in error_text for keyword in ['temporary', 'retry', 'again']):
            return ErrorCategory.TRANSIENT
        
        return ErrorCategory.SYSTEM
    
    def _determine_severity(
        self, 
        category: ErrorCategory, 
        error: Exception, 
        context: Optional[Dict[str, Any]]
    ) -> ErrorSeverity:
        """Determine error severity based on category and context."""
        
        # Critical errors that prevent system operation
        if category == ErrorCategory.AUTHENTICATION:
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        if category in [ErrorCategory.PERMANENT, ErrorCategory.SYSTEM]:
            return ErrorSeverity.HIGH
        
        # Medium severity errors
        if category in [ErrorCategory.RATE_LIMIT, ErrorCategory.TIMEOUT]:
            return ErrorSeverity.MEDIUM
        
        # Low severity errors
        return ErrorSeverity.LOW
    
    def _generate_user_message(
        self, 
        category: ErrorCategory, 
        error: Exception, 
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Generate a user-friendly error message."""
        
        messages = {
            ErrorCategory.AUTHENTICATION: (
                "Authentication failed. Please check your API keys and ensure they are valid and properly configured."
            ),
            ErrorCategory.RATE_LIMIT: (
                "API rate limit exceeded. The service is temporarily throttling requests. Please wait a moment before trying again."
            ),
            ErrorCategory.NETWORK: (
                "Network connection error. Please check your internet connection and try again."
            ),
            ErrorCategory.TIMEOUT: (
                "Request timed out. The service is taking longer than expected to respond. Please try again."
            ),
            ErrorCategory.USER: (
                "Invalid input or request. Please check your input parameters and try again."
            ),
            ErrorCategory.SYSTEM: (
                "A system error occurred. The service may be experiencing temporary issues. Please try again later."
            ),
            ErrorCategory.TRANSIENT: (
                "A temporary error occurred. The system will automatically retry the request."
            ),
            ErrorCategory.PERMANENT: (
                "A permanent error has occurred. Manual intervention may be required."
            )
        }
        
        return messages.get(category, "An unexpected error occurred. Please try again or contact support.")
    
    def _generate_suggested_action(
        self, 
        category: ErrorCategory, 
        error: Exception, 
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Generate suggested action for the user."""
        
        actions = {
            ErrorCategory.AUTHENTICATION: "Verify and update your API keys in the configuration",
            ErrorCategory.RATE_LIMIT: "Wait before making additional requests, consider reducing request frequency",
            ErrorCategory.NETWORK: "Check internet connection, verify firewall settings",
            ErrorCategory.TIMEOUT: "Retry the request, consider increasing timeout values if the issue persists",
            ErrorCategory.USER: "Review and correct the input parameters",
            ErrorCategory.SYSTEM: "Retry the request after a short delay, contact support if the issue persists",
            ErrorCategory.TRANSIENT: "The system will automatically handle this error",
            ErrorCategory.PERMANENT: "Contact support or check system logs for detailed error information"
        }
        
        return actions.get(category, "Contact support for assistance")
    
    def _log_classification(self, classification: ErrorClassification) -> None:
        """Log the error classification with structured data."""
        log_data = {
            "category": classification.category.value,
            "severity": classification.severity.value,
            "is_retryable": classification.is_retryable,
            "correlation_id": classification.correlation_id,
            "error_type": classification.technical_details.get("error_type"),
            "timestamp": classification.technical_details.get("timestamp")
        }
        
        # Use appropriate log level based on severity
        if classification.severity == ErrorSeverity.CRITICAL:
            self.logger.critical("Error classified", extra=log_data)
        elif classification.severity == ErrorSeverity.HIGH:
            self.logger.error("Error classified", extra=log_data)
        elif classification.severity == ErrorSeverity.MEDIUM:
            self.logger.warning("Error classified", extra=log_data)
        else:
            self.logger.info("Error classified", extra=log_data)
    
    def get_handling_strategy(self, category: ErrorCategory) -> ErrorHandlingStrategy:
        """Get the handling strategy for a specific error category."""
        return self.handling_strategies.get(category, self.handling_strategies[ErrorCategory.SYSTEM])
    
    def update_handling_strategy(self, category: ErrorCategory, strategy: ErrorHandlingStrategy) -> None:
        """Update the handling strategy for a specific error category."""
        self.handling_strategies[category] = strategy
        self.logger.info(f"Updated handling strategy for {category.value}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get statistics about error classifications (would need to track over time)."""
        # This would be enhanced with actual statistics tracking
        return {
            "categories_configured": len(self.error_patterns),
            "strategies_configured": len(self.handling_strategies),
            "total_patterns": sum(len(patterns) for patterns in self.error_patterns.values())
        }


class ErrorHandler:
    """Handles errors based on their classification."""
    
    def __init__(self, classifier: ErrorClassifier):
        self.classifier = classifier
        self.logger = get_logger(__name__)
        self._error_counts = {}  # Track error counts for alerting
    
    async def handle_error(
        self, 
        error: Exception, 
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Handle an error based on its classification.
        
        Returns:
            Tuple[should_retry: bool, user_message: Optional[str]]
        """
        classification = self.classifier.classify_error(error, context, correlation_id)
        strategy = self.classifier.get_handling_strategy(classification.category)
        
        # Track error for alerting
        self._track_error(classification)
        
        # Determine if we should alert
        if strategy.should_alert:
            await self._send_alert(classification)
        
        # Log structured error information
        await self._log_structured_error(classification, strategy)
        
        # Return handling decision
        should_retry = classification.is_retryable
        user_message = classification.user_message if strategy.user_visible else None
        
        return should_retry, user_message
    
    def _track_error(self, classification: ErrorClassification) -> None:
        """Track error occurrence for monitoring and alerting."""
        category_key = classification.category.value
        current_count = self._error_counts.get(category_key, 0)
        self._error_counts[category_key] = current_count + 1
        
        # Log error tracking
        self.logger.debug(f"Error count for {category_key}: {self._error_counts[category_key]}")
    
    async def _send_alert(self, classification: ErrorClassification) -> None:
        """Send alert for critical errors (placeholder for actual alerting system)."""
        alert_message = (
            f"ALERT: {classification.severity.value.upper()} error - "
            f"{classification.category.value} - {classification.user_message}"
        )
        
        # In a real system, this would integrate with alerting systems
        # like PagerDuty, Slack, email, etc.
        self.logger.error(f"ALERT TRIGGERED: {alert_message}", extra={
            "alert": True,
            "category": classification.category.value,
            "severity": classification.severity.value,
            "correlation_id": classification.correlation_id
        })
    
    async def _log_structured_error(
        self, 
        classification: ErrorClassification, 
        strategy: ErrorHandlingStrategy
    ) -> None:
        """Log structured error information for monitoring and debugging."""
        structured_log = {
            "error_classification": {
                "category": classification.category.value,
                "severity": classification.severity.value,
                "is_retryable": classification.is_retryable,
                "correlation_id": classification.correlation_id
            },
            "handling_strategy": {
                "max_retries": strategy.max_retries,
                "should_alert": strategy.should_alert,
                "should_fallback": strategy.should_fallback,
                "user_visible": strategy.user_visible
            },
            "technical_details": classification.technical_details,
            "suggested_action": classification.suggested_action
        }
        
        # Use enhanced logger if available for structured logging
        if hasattr(self.logger, 'log_error_classification'):
            self.logger.log_error_classification(structured_log)
        else:
            self.logger.error("Structured error log", extra=structured_log)
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of handled errors."""
        return {
            "total_errors": sum(self._error_counts.values()),
            "errors_by_category": self._error_counts.copy(),
            "categories_seen": len(self._error_counts)
        }
    
    def reset_error_counts(self) -> None:
        """Reset error tracking counts."""
        self._error_counts.clear()
        self.logger.info("Error counts reset")


# Global error classification system
_error_classifier = None
_error_handler = None

def get_error_classifier() -> ErrorClassifier:
    """Get the global error classifier instance."""
    global _error_classifier
    if _error_classifier is None:
        _error_classifier = ErrorClassifier()
    return _error_classifier

def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance."""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler(get_error_classifier())
    return _error_handler