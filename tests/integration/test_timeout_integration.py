#!/usr/bin/env python3
"""Test timeout management integration with the main system."""

import asyncio
import os
import sys

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.llm_judge.infrastructure.config.config import load_config, setup_logging
from llm_judge_simple import LLMJudge


async def test_timeout_integration():
    """Test that the timeout management system is working correctly."""
    print("🔧 Testing Timeout Management Integration")
    
    # Load configuration
    try:
        config = load_config()
        logger = setup_logging(config)
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")
        return False
    
    # Test provider initialization with timeout configuration
    try:
        # Test with mock mode to avoid API calls
        original_mode = os.environ.get('LLM_MODE', 'mock')
        os.environ['LLM_MODE'] = 'mock'
        
        judge = LLMJudge(config, logger)
        
        # Restore original mode
        if original_mode:
            os.environ['LLM_MODE'] = original_mode
        
        print("✅ LLMJudge initialized successfully with timeout management")
        
        # Test evaluation with timeout awareness
        from llm_judge_simple import CandidateResponse
        
        candidate = CandidateResponse(
            prompt="What is the capital of France?",
            response="Paris is the capital of France."
        )
        
        evaluation = await judge.evaluate_response(candidate, criteria="accuracy")
        
        print(f"✅ Evaluation completed: score={evaluation.score}")
        
        # Test comparison
        candidate_a = CandidateResponse(
            prompt="What is the capital of France?",
            response="Paris is the capital of France."
        )
        candidate_b = CandidateResponse(
            prompt="What is the capital of France?",
            response="The capital of France is Paris."
        )
        
        comparison = await judge.compare_responses(candidate_a, candidate_b)
        
        print(f"✅ Comparison completed: winner={comparison.get('winner', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Timeout integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        if 'judge' in locals():
            try:
                await judge.close()
            except:
                pass


async def test_timeout_configuration():
    """Test that timeout configuration is loaded correctly."""
    print("⚙️  Testing Timeout Configuration")
    
    try:
        config = load_config()
        
        # Check that timeout configurations are present
        assert hasattr(config, 'openai_request_timeout'), "Missing openai_request_timeout"
        assert hasattr(config, 'anthropic_request_timeout'), "Missing anthropic_request_timeout"
        assert hasattr(config, 'openai_connect_timeout'), "Missing openai_connect_timeout"
        assert hasattr(config, 'anthropic_connect_timeout'), "Missing anthropic_connect_timeout"
        
        print(f"✅ OpenAI request timeout: {config.openai_request_timeout}s")
        print(f"✅ Anthropic request timeout: {config.anthropic_request_timeout}s")
        print(f"✅ OpenAI connect timeout: {config.openai_connect_timeout}s")
        print(f"✅ Anthropic connect timeout: {config.anthropic_connect_timeout}s")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


async def main():
    """Run all timeout management tests."""
    print("🚀 Starting Timeout Management Integration Tests\n")
    
    tests = [
        ("Configuration Loading", test_timeout_configuration()),
        ("System Integration", test_timeout_integration())
    ]
    
    results = []
    for test_name, test_coro in tests:
        print(f"\n📋 Running {test_name} Test:")
        print("=" * 50)
        
        try:
            result = await test_coro
            results.append((test_name, result))
            
            if result:
                print(f"✅ {test_name} test PASSED")
            else:
                print(f"❌ {test_name} test FAILED")
                
        except Exception as e:
            print(f"❌ {test_name} test ERROR: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TIMEOUT MANAGEMENT INTEGRATION TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:.<40} {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All timeout management integration tests PASSED!")
        return True
    else:
        print("💥 Some timeout management integration tests FAILED!")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)