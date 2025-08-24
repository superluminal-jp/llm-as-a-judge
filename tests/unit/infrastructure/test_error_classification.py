"""Tests for error classification system."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio

from src.llm_judge.infrastructure.resilience.error_classification import (
    ErrorClassifier, ErrorHandler, ErrorCategory, ErrorSeverity, 
    ErrorClassification, ErrorHandlingStrategy,
    get_error_classifier, get_error_handler
)


class TestErrorClassifier:
    """Test error classification functionality."""
    
    @pytest.fixture
    def classifier(self):
        """Create error classifier for testing."""
        return ErrorClassifier()
    
    def test_authentication_error_classification(self, classifier):
        """Test classification of authentication errors."""
        errors = [
            Exception("Authentication failed"),
            Exception("Invalid API key"),
            Exception("401 Unauthorized"),
            Exception("403 Forbidden")
        ]
        
        for error in errors:
            classification = classifier.classify_error(error)
            assert classification.category == ErrorCategory.AUTHENTICATION
            assert classification.severity == ErrorSeverity.CRITICAL
            assert not classification.is_retryable
    
    def test_rate_limit_error_classification(self, classifier):
        """Test classification of rate limit errors."""
        errors = [
            Exception("Rate limit exceeded"),
            Exception("Too many requests"),
            Exception("429 Too Many Requests"),
            Exception("Quota exceeded")
        ]
        
        for error in errors:
            classification = classifier.classify_error(error)
            assert classification.category == ErrorCategory.RATE_LIMIT
            assert classification.severity == ErrorSeverity.MEDIUM
            assert classification.is_retryable
    
    def test_network_error_classification(self, classifier):
        """Test classification of network errors."""
        errors = [
            Exception("Connection failed"),
            Exception("Network error occurred"),
            Exception("Host unreachable"),
            Exception("DNS resolution failed")
        ]
        
        for error in errors:
            classification = classifier.classify_error(error)
            assert classification.category == ErrorCategory.NETWORK
            assert classification.severity == ErrorSeverity.LOW
            assert classification.is_retryable
    
    def test_timeout_error_classification(self, classifier):
        """Test classification of timeout errors."""
        errors = [
            Exception("Request timed out"),
            Exception("Operation timeout"),
            TimeoutError("Connection timeout"),
            Exception("Deadline exceeded")
        ]
        
        for error in errors:
            classification = classifier.classify_error(error)
            assert classification.category == ErrorCategory.TIMEOUT
            assert classification.severity == ErrorSeverity.MEDIUM
            assert classification.is_retryable
    
    def test_user_error_classification(self, classifier):
        """Test classification of user input errors."""
        errors = [
            Exception("Invalid input provided"),
            Exception("Validation failed"),
            Exception("400 Bad Request"),
            Exception("Malformed request")
        ]
        
        for error in errors:
            classification = classifier.classify_error(error)
            assert classification.category == ErrorCategory.USER
            assert classification.severity == ErrorSeverity.LOW
            assert not classification.is_retryable
    
    def test_system_error_classification(self, classifier):
        """Test classification of system errors."""
        errors = [
            Exception("500 Internal Server Error"),
            Exception("Service unavailable"),
            Exception("502 Bad Gateway"),
            Exception("503 Service Unavailable")
        ]
        
        for error in errors:
            classification = classifier.classify_error(error)
            assert classification.category == ErrorCategory.SYSTEM
            assert classification.severity == ErrorSeverity.HIGH
            assert classification.is_retryable
    
    def test_error_classification_with_context(self, classifier):
        """Test error classification with additional context."""
        error = Exception("Generic error")
        context = {
            "service": "anthropic",
            "operation": "create_message",
            "attempt": 2
        }
        
        classification = classifier.classify_error(error, context)
        
        assert "context" in classification.technical_details
        assert classification.technical_details["context"]["service"] == "anthropic"
        assert classification.technical_details["context"]["attempt"] == 2
    
    def test_error_classification_with_correlation_id(self, classifier):
        """Test error classification with correlation ID."""
        error = Exception("Test error")
        correlation_id = "test-correlation-123"
        
        classification = classifier.classify_error(error, correlation_id=correlation_id)
        
        assert classification.correlation_id == correlation_id
    
    def test_user_message_generation(self, classifier):
        """Test user-friendly message generation."""
        test_cases = [
            (Exception("Authentication failed"), ErrorCategory.AUTHENTICATION, "API keys"),
            (Exception("Rate limit exceeded"), ErrorCategory.RATE_LIMIT, "rate limit"),
            (Exception("Connection failed"), ErrorCategory.NETWORK, "internet connection"),
            (Exception("Request timed out"), ErrorCategory.TIMEOUT, "timed out"),
            (Exception("Invalid input"), ErrorCategory.USER, "input parameters")
        ]
        
        for error, expected_category, expected_keyword in test_cases:
            classification = classifier.classify_error(error)
            assert classification.category == expected_category
            assert expected_keyword.lower() in classification.user_message.lower()
    
    def test_suggested_action_generation(self, classifier):
        """Test suggested action generation."""
        test_cases = [
            (Exception("Authentication failed"), "API keys"),
            (Exception("Rate limit exceeded"), "reducing request frequency"),
            (Exception("Connection failed"), "internet connection"),
            (Exception("Request timed out"), "Retry the request"),
            (Exception("Invalid input"), "input parameters")
        ]
        
        for error, expected_keyword in test_cases:
            classification = classifier.classify_error(error)
            assert expected_keyword.lower() in classification.suggested_action.lower()
    
    def test_handling_strategy_retrieval(self, classifier):
        """Test retrieval of handling strategies."""
        strategies = [
            (ErrorCategory.AUTHENTICATION, 0),  # No retries for auth errors
            (ErrorCategory.RATE_LIMIT, 5),     # More retries for rate limits
            (ErrorCategory.NETWORK, 3),        # Standard retries for network
            (ErrorCategory.USER, 0)            # No retries for user errors
        ]
        
        for category, expected_max_retries in strategies:
            strategy = classifier.get_handling_strategy(category)
            assert strategy.max_retries == expected_max_retries
    
    def test_update_handling_strategy(self, classifier):
        """Test updating handling strategies."""
        new_strategy = ErrorHandlingStrategy(
            max_retries=10,
            base_delay=5.0,
            backoff_multiplier=3.0,
            should_alert=True,
            should_fallback=False,
            user_visible=True
        )
        
        classifier.update_handling_strategy(ErrorCategory.NETWORK, new_strategy)
        retrieved_strategy = classifier.get_handling_strategy(ErrorCategory.NETWORK)
        
        assert retrieved_strategy.max_retries == 10
        assert retrieved_strategy.base_delay == 5.0
        assert retrieved_strategy.backoff_multiplier == 3.0
    
    def test_error_statistics(self, classifier):
        """Test error statistics retrieval."""
        stats = classifier.get_error_statistics()
        
        assert "categories_configured" in stats
        assert "strategies_configured" in stats
        assert "total_patterns" in stats
        assert stats["categories_configured"] > 0
        assert stats["strategies_configured"] > 0


class TestErrorHandler:
    """Test error handling functionality."""
    
    @pytest.fixture
    def classifier(self):
        """Create error classifier for testing."""
        return ErrorClassifier()
    
    @pytest.fixture
    def handler(self, classifier):
        """Create error handler for testing."""
        return ErrorHandler(classifier)
    
    @pytest.mark.asyncio
    async def test_handle_retryable_error(self, handler):
        """Test handling of retryable errors."""
        error = Exception("Network connection failed")
        context = {"service": "test", "operation": "test_op"}
        
        should_retry, user_message = await handler.handle_error(error, context)
        
        assert should_retry is True
        assert user_message is None  # Network errors are not user-visible by default
    
    @pytest.mark.asyncio
    async def test_handle_non_retryable_error(self, handler):
        """Test handling of non-retryable errors."""
        error = Exception("Authentication failed")
        context = {"service": "test", "operation": "test_op"}
        
        should_retry, user_message = await handler.handle_error(error, context)
        
        assert should_retry is False
        assert user_message is not None
        assert "authentication" in user_message.lower()
    
    @pytest.mark.asyncio
    async def test_handle_user_visible_error(self, handler):
        """Test handling of user-visible errors."""
        error = Exception("Invalid input provided")
        context = {"service": "test", "operation": "test_op"}
        
        should_retry, user_message = await handler.handle_error(error, context)
        
        assert should_retry is False
        assert user_message is not None
        assert "input" in user_message.lower()
    
    @pytest.mark.asyncio
    async def test_error_tracking(self, handler):
        """Test error occurrence tracking."""
        errors = [
            Exception("Rate limit exceeded"),
            Exception("Rate limit exceeded"),
            Exception("Network error"),
            Exception("Authentication failed")
        ]
        
        for error in errors:
            await handler.handle_error(error)
        
        summary = handler.get_error_summary()
        
        assert summary["total_errors"] == 4
        assert summary["errors_by_category"]["rate_limit"] == 2
        assert summary["errors_by_category"]["network"] == 1
        assert summary["errors_by_category"]["authentication"] == 1
        assert summary["categories_seen"] == 3
    
    @pytest.mark.asyncio
    async def test_alert_triggering(self, handler):
        """Test alert triggering for critical errors."""
        with patch.object(handler.logger, 'error') as mock_log:
            error = Exception("Authentication failed")
            await handler.handle_error(error)
            
            # Check that an alert was logged (should be called twice - once for alert, once for structured log)
            assert mock_log.call_count >= 1
            
            # Check if any of the calls contained alert information
            calls_str = str(mock_log.call_args_list)
            alert_triggered = "ALERT" in calls_str or "alert" in calls_str.lower()
            assert alert_triggered
    
    def test_reset_error_counts(self, handler):
        """Test resetting error counts."""
        # Add some errors to track
        handler._error_counts = {"test": 5, "other": 3}
        
        handler.reset_error_counts()
        
        summary = handler.get_error_summary()
        assert summary["total_errors"] == 0
        assert len(summary["errors_by_category"]) == 0


class TestGlobalInstances:
    """Test global error classification instances."""
    
    def test_get_error_classifier_singleton(self):
        """Test that get_error_classifier returns singleton instance."""
        classifier1 = get_error_classifier()
        classifier2 = get_error_classifier()
        
        assert classifier1 is classifier2
        assert isinstance(classifier1, ErrorClassifier)
    
    def test_get_error_handler_singleton(self):
        """Test that get_error_handler returns singleton instance."""
        handler1 = get_error_handler()
        handler2 = get_error_handler()
        
        assert handler1 is handler2
        assert isinstance(handler1, ErrorHandler)
    
    def test_error_handler_uses_classifier(self):
        """Test that error handler uses the global classifier."""
        classifier = get_error_classifier()
        handler = get_error_handler()
        
        assert handler.classifier is classifier


class TestRealWorldScenarios:
    """Test real-world error scenarios."""
    
    @pytest.fixture
    def classifier(self):
        """Create error classifier for testing."""
        return ErrorClassifier()
    
    def test_openai_authentication_error(self, classifier):
        """Test classification of OpenAI authentication error."""
        error = Exception("Error code: 401 - {'error': {'message': 'Incorrect API key provided'}}")
        classification = classifier.classify_error(error)
        
        assert classification.category == ErrorCategory.AUTHENTICATION
        assert classification.severity == ErrorSeverity.CRITICAL
        assert not classification.is_retryable
    
    def test_anthropic_rate_limit_error(self, classifier):
        """Test classification of Anthropic rate limit error."""
        error = Exception("Error code: 429 - {'error': {'type': 'rate_limit_error', 'message': 'Rate limit exceeded'}}")
        classification = classifier.classify_error(error)
        
        assert classification.category == ErrorCategory.RATE_LIMIT
        assert classification.severity == ErrorSeverity.MEDIUM
        assert classification.is_retryable
    
    def test_connection_timeout_error(self, classifier):
        """Test classification of connection timeout error."""
        error = Exception("HTTPSConnectionPool(host='api.openai.com', port=443): Read timed out.")
        classification = classifier.classify_error(error)
        
        assert classification.category == ErrorCategory.TIMEOUT
        assert classification.severity == ErrorSeverity.MEDIUM
        assert classification.is_retryable
    
    def test_server_error_5xx(self, classifier):
        """Test classification of server errors."""
        errors = [
            Exception("Error code: 500 - Internal server error"),
            Exception("Error code: 502 - Bad gateway"),
            Exception("Error code: 503 - Service temporarily unavailable")
        ]
        
        for error in errors:
            classification = classifier.classify_error(error)
            assert classification.category == ErrorCategory.SYSTEM
            assert classification.severity == ErrorSeverity.HIGH
            assert classification.is_retryable
    
    def test_malformed_request_error(self, classifier):
        """Test classification of malformed request errors."""
        error = Exception("Error code: 400 - {'error': {'message': 'Invalid request format'}}")
        classification = classifier.classify_error(error)
        
        assert classification.category == ErrorCategory.USER
        assert classification.severity == ErrorSeverity.LOW
        assert not classification.is_retryable


@pytest.mark.asyncio
async def test_error_classification_integration():
    """Integration test for error classification system."""
    classifier = ErrorClassifier()
    handler = ErrorHandler(classifier)
    
    # Test a sequence of different errors
    test_errors = [
        (Exception("Authentication failed"), False, True),  # Should not retry, user visible
        (Exception("Rate limit exceeded"), True, False),   # Should retry, not user visible  
        (Exception("Connection failed"), True, False),     # Should retry, not user visible
        (Exception("Invalid input"), False, True),         # Should not retry, user visible
    ]
    
    results = []
    for error, expected_retry, expected_user_visible in test_errors:
        should_retry, user_message = await handler.handle_error(error, {"test": "context"})
        results.append((should_retry, user_message is not None))
        
        # Verify expectations
        assert should_retry == expected_retry
        assert (user_message is not None) == expected_user_visible
    
    # Check error summary
    summary = handler.get_error_summary()
    assert summary["total_errors"] == 4
    assert summary["categories_seen"] >= 4  # Should have seen multiple categories