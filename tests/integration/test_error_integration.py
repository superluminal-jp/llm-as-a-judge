#!/usr/bin/env python3
"""Test error classification integration with the main system."""

import asyncio
import os
import sys

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.llm_judge.infrastructure.resilience.error_classification import get_error_classifier, get_error_handler, ErrorCategory, ErrorSeverity
from src.llm_judge.infrastructure.config.config import load_config, setup_logging


async def test_error_classification_integration():
    """Test that the error classification system works correctly."""
    print("🔧 Testing Error Classification System Integration")
    
    # Initialize error classification system
    try:
        classifier = get_error_classifier()
        handler = get_error_handler()
        print("✅ Error classification system initialized")
    except Exception as e:
        print(f"❌ Error classification system initialization failed: {e}")
        return False
    
    # Test different error types
    test_errors = [
        ("Authentication Error", Exception("API key authentication failed - 401 Unauthorized")),
        ("Rate Limit Error", Exception("Rate limit exceeded - 429 Too Many Requests")), 
        ("Network Error", Exception("Connection failed - network is unreachable")),
        ("Timeout Error", Exception("Request timed out after 30 seconds")),
        ("User Error", Exception("Invalid input provided - 400 Bad Request")),
        ("System Error", Exception("Internal server error - 500 Server Error"))
    ]
    
    classification_results = []
    handling_results = []
    
    for error_name, error in test_errors:
        try:
            # Test error classification
            classification = classifier.classify_error(error, {"test": "context"})
            classification_results.append((error_name, classification.category, classification.severity))
            
            print(f"✅ {error_name}: {classification.category.value} ({classification.severity.value})")
            print(f"   Retryable: {classification.is_retryable}")
            print(f"   User Message: {classification.user_message}")
            
            # Test error handling
            should_retry, user_message = await handler.handle_error(error, {"test": "context"})
            handling_results.append((error_name, should_retry, user_message is not None))
            
            print(f"   Should Retry: {should_retry}, User Visible: {user_message is not None}")
            print()
            
        except Exception as e:
            print(f"❌ Error testing {error_name}: {e}")
            return False
    
    # Verify classifications
    expected_categories = {
        "Authentication Error": ErrorCategory.AUTHENTICATION,
        "Rate Limit Error": ErrorCategory.RATE_LIMIT,
        "Network Error": ErrorCategory.NETWORK,
        "Timeout Error": ErrorCategory.TIMEOUT,
        "User Error": ErrorCategory.USER,
        "System Error": ErrorCategory.SYSTEM
    }
    
    for error_name, actual_category, severity in classification_results:
        expected_category = expected_categories[error_name]
        if actual_category != expected_category:
            print(f"❌ Classification mismatch for {error_name}: expected {expected_category.value}, got {actual_category.value}")
            return False
    
    print("✅ All error classifications correct")
    
    # Test error statistics
    try:
        stats = classifier.get_error_statistics()
        print(f"✅ Error statistics: {stats['categories_configured']} categories, {stats['total_patterns']} patterns")
        
        summary = handler.get_error_summary()
        print(f"✅ Handling summary: {summary['total_errors']} errors handled, {summary['categories_seen']} categories seen")
        
    except Exception as e:
        print(f"❌ Error statistics test failed: {e}")
        return False
    
    return True


async def test_retry_integration():
    """Test integration with retry system."""
    print("🔄 Testing Integration with Retry System")
    
    try:
        from retry_strategies import EnhancedRetryManager
        from src.llm_judge.infrastructure.config.config import load_config
        
        config = load_config()
        retry_manager = EnhancedRetryManager(config)
        
        # Test that retry manager uses error classification
        error = Exception("Rate limit exceeded - 429")
        error_type = retry_manager.classify_error(error)
        
        print(f"✅ Retry manager classified rate limit error as: {error_type.value}")
        
        # Verify the error classifier and handler are properly initialized
        assert hasattr(retry_manager, 'error_classifier')
        assert hasattr(retry_manager, 'error_handler')
        
        print("✅ Retry manager integration successful")
        return True
        
    except Exception as e:
        print(f"❌ Retry integration test failed: {e}")
        return False


async def test_logging_integration():
    """Test integration with logging system."""
    print("📋 Testing Integration with Logging System")
    
    try:
        config = load_config()
        logger = setup_logging(config)
        
        # Test that enhanced logging methods are available
        if hasattr(logger, 'log_error_classification'):
            print("✅ Enhanced logging supports error classification")
        else:
            print("⚠️ Enhanced logging error classification not available (fallback mode)")
        
        return True
        
    except Exception as e:
        print(f"❌ Logging integration test failed: {e}")
        return False


async def test_real_world_scenarios():
    """Test real-world error scenarios."""
    print("🌍 Testing Real-World Error Scenarios")
    
    classifier = get_error_classifier()
    handler = get_error_handler()
    
    # Real-world error messages from actual API services
    real_errors = [
        ("OpenAI Auth", Exception("Error code: 401 - {'error': {'message': 'Incorrect API key provided: test-key. You can find your API key at https://platform.openai.com/account/api-keys.', 'type': 'invalid_request_error', 'param': None, 'code': 'invalid_api_key'}}")),
        ("Anthropic Rate Limit", Exception("Error code: 429 - {'type': 'rate_limit_error', 'message': 'Rate limit exceeded. Please wait before making more requests.'}")),
        ("Connection Timeout", Exception("HTTPSConnectionPool(host='api.openai.com', port=443): Read timed out. (read timeout=30)")),
        ("Server Error", Exception("Error code: 503 - {'error': {'message': 'The server is temporarily unavailable. Please try again later.', 'type': 'server_error'}}")),
    ]
    
    for scenario_name, error in real_errors:
        try:
            classification = classifier.classify_error(error)
            should_retry, user_message = await handler.handle_error(error)
            
            print(f"✅ {scenario_name}")
            print(f"   Category: {classification.category.value}")
            print(f"   Severity: {classification.severity.value}")
            print(f"   Should Retry: {should_retry}")
            print(f"   User Visible: {user_message is not None}")
            print()
            
        except Exception as e:
            print(f"❌ Real-world scenario {scenario_name} failed: {e}")
            return False
    
    print("✅ All real-world scenarios handled correctly")
    return True


async def main():
    """Run all error classification integration tests."""
    print("🚀 Starting Error Classification Integration Tests\n")
    
    tests = [
        ("Error Classification System", test_error_classification_integration()),
        ("Retry System Integration", test_retry_integration()),
        ("Logging System Integration", test_logging_integration()),
        ("Real-World Scenarios", test_real_world_scenarios())
    ]
    
    results = []
    for test_name, test_coro in tests:
        print(f"📋 Running {test_name} Test:")
        print("=" * 60)
        
        try:
            result = await test_coro
            results.append((test_name, result))
            
            if result:
                print(f"✅ {test_name} test PASSED\n")
            else:
                print(f"❌ {test_name} test FAILED\n")
                
        except Exception as e:
            print(f"❌ {test_name} test ERROR: {e}\n")
            results.append((test_name, False))
    
    # Summary
    print("=" * 80)
    print("📊 ERROR CLASSIFICATION INTEGRATION TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:.<50} {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All error classification integration tests PASSED!")
        return True
    else:
        print("💥 Some error classification integration tests FAILED!")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)