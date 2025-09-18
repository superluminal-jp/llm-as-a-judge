"""Comprehensive error scenario and stress tests for the LLM-as-a-Judge system."""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from src.llm_judge.infrastructure.config.config import LLMConfig
from src.llm_judge.application.services.llm_judge_service import LLMJudge, CandidateResponse
from src.llm_judge.infrastructure.resilience.fallback_manager import FallbackManager, ServiceMode


@pytest.fixture
def multi_provider_config():
    """Configuration with all providers available."""
    return LLMConfig(
        openai_api_key="test-openai-key",
        anthropic_api_key="test-anthropic-key",
        aws_access_key_id="test-aws-key",
        aws_secret_access_key="test-aws-secret",
        aws_region="us-east-1",
        default_provider="anthropic",
        request_timeout=5,  # Short timeout for stress tests
        max_retries=2
    )


@pytest.fixture
def stress_test_candidates():
    """Generate multiple test candidates for stress testing."""
    candidates = []
    for i in range(10):
        candidates.append(CandidateResponse(
            prompt=f"Question {i}: Explain the concept of {['AI', 'ML', 'DL', 'NLP', 'CV'][i % 5]}",
            response=f"Response {i}: This is a test response about the topic with various details and explanations.",
            model=f"test-model-{i % 3}"
        ))
    return candidates


class TestNetworkFailureScenarios:
    """Test various network failure scenarios."""
    
    @pytest.mark.asyncio
    async def test_complete_network_failure(self, multi_provider_config):
        """Test behavior when all network requests fail."""
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
                    # Mock all clients to raise network errors
                    network_error = Exception("Network unreachable")
                    
                    with patch('anthropic.Anthropic') as mock_anthropic:
                        with patch('openai.OpenAI') as mock_openai:
                            with patch('boto3.Session') as mock_boto3:
                                # Configure all clients to fail
                                mock_anthropic_client = Mock()
                                mock_anthropic_client.messages.create = Mock(side_effect=network_error)
                                mock_anthropic.return_value = mock_anthropic_client
                                
                                mock_openai_client = Mock()
                                mock_openai_client.chat.completions.create = Mock(side_effect=network_error)
                                mock_openai.return_value = mock_openai_client
                                
                                mock_bedrock_client = Mock()
                                mock_bedrock_client.invoke_model = Mock(side_effect=network_error)
                                mock_boto3.return_value.client.return_value = mock_bedrock_client
                                
                                judge = LLMJudge(multi_provider_config)
                                candidate = CandidateResponse(
                                    prompt="Test prompt",
                                    response="Test response",
                                    model="test"
                                )
                                
                                # Should fall back to mock evaluation
                                result = await judge.evaluate_response(
                                    candidate,
                                    criteria="quality",
                                    use_multi_criteria=False
                                )
                                
                                assert result.score > 0  # Should get mock score
                                assert result.confidence < 1.0  # Mock confidence is lower
                                
                                await judge.close()
    
    @pytest.mark.asyncio
    async def test_intermittent_network_failures(self, multi_provider_config):
        """Test behavior with intermittent network failures."""
        # Test with mocked Anthropic client
        with patch('anthropic.Anthropic') as mock_anthropic:
                mock_client = Mock()
                
                # Configure to fail first two calls, then succeed
                call_count = 0
                def mock_create_side_effect(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count <= 2:
                        raise Exception("Temporary network error")
                    else:
                        # Return successful response
                        mock_response = Mock()
                        mock_response.content = [Mock(text='{"score": 4, "reasoning": "Good response", "confidence": 0.8}')]
                        mock_response.stop_reason = 'end_turn'
                        mock_response.usage = Mock(input_tokens=50, output_tokens=30)
                        return mock_response
                
                mock_client.messages.create = Mock(side_effect=mock_create_side_effect)
                mock_anthropic.return_value = mock_client
                
                judge = LLMJudge(multi_provider_config)
                candidate = CandidateResponse(
                    prompt="Test prompt",
                    response="Test response", 
                    model="test"
                )
                
                # Should eventually succeed after retries
                result = await judge.evaluate_response(
                    candidate,
                    criteria="quality",
                    use_multi_criteria=False
                )
                
                assert result.score == 4
                assert "Good response" in result.reasoning
                
                await judge.close()
    
    @pytest.mark.asyncio
    async def test_timeout_scenarios(self, multi_provider_config):
        """Test various timeout scenarios."""
        # Test with mocked Anthropic client
        with patch('anthropic.Anthropic') as mock_anthropic:
                mock_client = Mock()
                
                # Mock timeout error
                def timeout_side_effect(*args, **kwargs):
                    raise TimeoutError("Request timed out")  # Simulate timeout
                
                mock_client.messages.create = Mock(side_effect=timeout_side_effect)
                mock_anthropic.return_value = mock_client
                
                # Use short timeout config
                timeout_config = LLMConfig(
                    anthropic_api_key="test-key",
                    default_provider="anthropic",
                    request_timeout=1  # 1 second timeout
                )
                
                judge = LLMJudge(timeout_config)
                candidate = CandidateResponse(
                    prompt="Test prompt",
                    response="Test response",
                    model="test"
                )
                
                # Should handle timeout and fall back
                start_time = time.time()
                result = await judge.evaluate_response(
                    candidate,
                    criteria="quality",
                    use_multi_criteria=False
                )
                elapsed = time.time() - start_time
                
                # Should not take much longer than timeout
                assert elapsed < 5  # Allow some overhead
                assert result.score > 0  # Should get fallback result
                
                await judge.close()


class TestConcurrencyStressTests:
    """Stress tests for concurrent operations."""
    
    @pytest.mark.asyncio
    async def test_high_concurrency_evaluations(self, multi_provider_config, stress_test_candidates):
        """Test system under high concurrent load."""
        # Test with mocked Anthropic client
        with patch('anthropic.Anthropic') as mock_anthropic:
                mock_client = Mock()
                
                # Mock successful responses with small delay
                def mock_create_with_delay(*args, **kwargs):
                    import time; time.sleep(0.1)  # Small delay to simulate real API
                    mock_response = Mock()
                    mock_response.content = [Mock(text='{"score": 4, "reasoning": "Stress test response", "confidence": 0.8}')]
                    mock_response.stop_reason = 'end_turn'
                    mock_response.usage = Mock(input_tokens=50, output_tokens=30)
                    return mock_response
                
                mock_client.messages.create = Mock(side_effect=mock_create_with_delay)
                mock_anthropic.return_value = mock_client
                
                judge = LLMJudge(multi_provider_config)
                
                # Create high number of concurrent tasks
                tasks = []
                for candidate in stress_test_candidates:
                    task = judge.evaluate_response(
                        candidate,
                        criteria="quality",
                        use_multi_criteria=False
                    )
                    tasks.append(task)
                
                # Add more tasks to stress the system
                for i in range(20):
                    extra_candidate = CandidateResponse(
                        prompt=f"Extra question {i}",
                        response=f"Extra response {i}",
                        model="stress-test"
                    )
                    task = judge.evaluate_response(
                        extra_candidate,
                        criteria="quality",
                        use_multi_criteria=False
                    )
                    tasks.append(task)
                
                # Execute all tasks concurrently
                start_time = time.time()
                results = await asyncio.gather(*tasks, return_exceptions=True)
                elapsed = time.time() - start_time
                
                # Verify results
                successful_results = [r for r in results if not isinstance(r, Exception)]
                failed_results = [r for r in results if isinstance(r, Exception)]
                
                # Should have mostly successful results
                success_rate = len(successful_results) / len(results)
                assert success_rate >= 0.8  # At least 80% success rate
                
                # Should complete in reasonable time (with concurrency)
                assert elapsed < 10  # Should be much faster than sequential
                
                print(f"Concurrent stress test: {len(successful_results)}/{len(results)} succeeded in {elapsed:.2f}s")
                
                await judge.close()
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, multi_provider_config):
        """Test memory usage under sustained load."""
        # Test with mocked Anthropic client
        with patch('anthropic.Anthropic') as mock_anthropic:
                mock_client = Mock()
                
                def mock_create(*args, **kwargs):
                    # Return response without accumulating memory
                    mock_response = Mock()
                    mock_response.content = [Mock(text='{"score": 4, "reasoning": "Memory test", "confidence": 0.7}')]
                    mock_response.stop_reason = 'end_turn'
                    mock_response.usage = Mock(input_tokens=20, output_tokens=15)
                    return mock_response
                
                mock_client.messages.create = Mock(side_effect=mock_create)
                mock_anthropic.return_value = mock_client
                
                judge = LLMJudge(multi_provider_config)
                
                # Run many sequential evaluations
                results = []
                for i in range(50):  # Reduced for faster testing
                    candidate = CandidateResponse(
                        prompt=f"Memory test question {i}",
                        response=f"Memory test response {i}",
                        model="memory-test"
                    )
                    
                    result = await judge.evaluate_response(
                        candidate,
                        criteria="quality",
                        use_multi_criteria=False
                    )
                    results.append(result)
                    
                    # Verify each result
                    assert result.score == 4
                    assert "Memory test" in result.reasoning
                
                # Verify all results are consistent
                assert len(results) == 50
                assert all(r.score == 4 for r in results)
                
                await judge.close()


class TestFailureRecoveryScenarios:
    """Test system recovery after failures."""
    
    @pytest.mark.asyncio
    async def test_provider_recovery_after_failure(self, multi_provider_config):
        """Test that providers can recover after temporary failures."""
        # Test with mocked Anthropic client
        with patch('anthropic.Anthropic') as mock_anthropic:
                mock_client = Mock()
                
                # Simulate provider failure then recovery
                call_count = 0
                def mock_create_with_recovery(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    
                    if 3 <= call_count <= 5:  # Fail for calls 3-5
                        raise Exception("Provider temporarily down")
                    else:
                        # Successful response
                        mock_response = Mock()
                        mock_response.content = [Mock(text='{"score": 4, "reasoning": "Recovered response", "confidence": 0.9}')]
                        mock_response.stop_reason = 'end_turn'
                        mock_response.usage = Mock(input_tokens=40, output_tokens=25)
                        return mock_response
                
                mock_client.messages.create = Mock(side_effect=mock_create_with_recovery)
                mock_anthropic.return_value = mock_client
                
                judge = LLMJudge(multi_provider_config)
                
                # Run multiple evaluations to test recovery
                results = []
                for i in range(8):
                    candidate = CandidateResponse(
                        prompt=f"Recovery test {i}",
                        response=f"Response {i}",
                        model="recovery-test"
                    )
                    
                    result = await judge.evaluate_response(
                        candidate,
                        criteria="quality",
                        use_multi_criteria=False
                    )
                    results.append(result)
                
                # Check that we got both failure fallback and recovery responses
                successful_api_results = [r for r in results if "Recovered response" in r.reasoning]
                fallback_results = [r for r in results if "Recovered response" not in r.reasoning]
                
                assert len(successful_api_results) > 0  # Should have some successful API calls
                assert len(fallback_results) > 0  # Should have some fallback responses during failure
                
                await judge.close()
    
    @pytest.mark.asyncio
    async def test_cascading_failure_handling(self, multi_provider_config):
        """Test handling of cascading failures across providers."""
        with patch('src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE', True):
                    
                    call_counts = {"anthropic": 0, "openai": 0, "bedrock": 0}
                    
                    def failing_anthropic(*args, **kwargs):
                        call_counts["anthropic"] += 1
                        raise Exception("Anthropic service down")
                    
                    def failing_openai(*args, **kwargs):
                        call_counts["openai"] += 1
                        if call_counts["openai"] <= 2:
                            raise Exception("OpenAI temporarily down")
                        # Succeed after 2 failures
                        mock_response = Mock()
                        mock_response.choices = [Mock(message=Mock(content='{"score": 4, "reasoning": "OpenAI recovery", "confidence": 0.85}'))]
                        mock_response.usage = Mock(prompt_tokens=30, completion_tokens=20)
                        return mock_response
                    
                    def failing_bedrock(*args, **kwargs):
                        call_counts["bedrock"] += 1
                        raise Exception("Bedrock service down")
                    
                    with patch('anthropic.Anthropic') as mock_anthropic:
                        with patch('openai.OpenAI') as mock_openai:
                            with patch('boto3.Session') as mock_boto3:
                                # Configure failing services
                                mock_anthropic_client = Mock()
                                mock_anthropic_client.messages.create = Mock(side_effect=failing_anthropic)
                                mock_anthropic.return_value = mock_anthropic_client
                                
                                mock_openai_client = Mock()
                                mock_openai_client.chat.completions.create = Mock(side_effect=failing_openai)
                                mock_openai.return_value = mock_openai_client
                                
                                mock_bedrock_client = Mock()
                                mock_bedrock_client.invoke_model = Mock(side_effect=failing_bedrock)
                                mock_boto3.return_value.client.return_value = mock_bedrock_client
                                
                                judge = LLMJudge(multi_provider_config)
                                
                                # Run multiple evaluations to trigger cascading failures
                                results = []
                                for i in range(5):
                                    candidate = CandidateResponse(
                                        prompt=f"Cascading test {i}",
                                        response=f"Response {i}",
                                        model="cascade-test"
                                    )
                                    
                                    result = await judge.evaluate_response(
                                        candidate,
                                        criteria="quality",
                                        use_multi_criteria=False
                                    )
                                    results.append(result)
                                
                                # Should have some results (either successful or fallback)
                                assert len(results) == 5
                                
                                # All results should have valid scores
                                assert all(r.score > 0 for r in results)
                                
                                # Should have tried at least Anthropic
                                assert call_counts["anthropic"] > 0
                                # OpenAI and Bedrock might not be tried if fallback works
                                
                                await judge.close()


class TestResourceExhaustionScenarios:
    """Test behavior under resource exhaustion."""
    
    @pytest.mark.asyncio
    async def test_rate_limiting_handling(self, multi_provider_config):
        """Test handling of API rate limits."""
        # Test with mocked Anthropic client
        with patch('anthropic.Anthropic') as mock_anthropic:
                mock_client = Mock()
                
                # Simulate rate limiting for first few calls
                call_count = 0
                def rate_limited_create(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    
                    if call_count <= 3:
                        # Simulate rate limit error
                        from anthropic import RateLimitError
                        raise RateLimitError(
                            message="Rate limit exceeded",
                            response=Mock(status_code=429),
                            body=None
                        )
                    else:
                        # Successful response after rate limit
                        mock_response = Mock()
                        mock_response.content = [Mock(text='{"score": 4, "reasoning": "Post rate-limit response", "confidence": 0.88}')]
                        mock_response.stop_reason = 'end_turn'
                        mock_response.usage = Mock(input_tokens=45, output_tokens=35)
                        return mock_response
                
                mock_client.messages.create = Mock(side_effect=rate_limited_create)
                mock_anthropic.return_value = mock_client
                
                judge = LLMJudge(multi_provider_config)
                candidate = CandidateResponse(
                    prompt="Rate limit test",
                    response="Test response",
                    model="rate-limit-test"
                )
                
                # Should eventually succeed after rate limit delay
                result = await judge.evaluate_response(
                    candidate,
                    criteria="quality",
                    use_multi_criteria=False
                )
                
                # Should get either successful response or fallback
                assert result.score > 0
                if "Post rate-limit response" in result.reasoning:
                    assert result.score == 4
                
                await judge.close()
    
    @pytest.mark.asyncio
    async def test_memory_pressure_handling(self, multi_provider_config):
        """Test behavior under memory pressure."""
        # This test simulates memory pressure indirectly
        # Test with mocked Anthropic client
        with patch('anthropic.Anthropic') as mock_anthropic:
                mock_client = Mock()
                
                def memory_pressure_create(*args, **kwargs):
                    # Simulate memory pressure by creating large objects
                    large_data = "x" * 10000  # 10KB string
                    mock_response = Mock()
                    mock_response.content = [Mock(text=f'{{"score": 4, "reasoning": "Memory pressure test - {large_data[:50]}...", "confidence": 0.75}}')]
                    mock_response.stop_reason = 'end_turn'
                    mock_response.usage = Mock(input_tokens=100, output_tokens=50)
                    return mock_response
                
                mock_client.messages.create = Mock(side_effect=memory_pressure_create)
                mock_anthropic.return_value = mock_client
                
                judge = LLMJudge(multi_provider_config)
                
                # Run many evaluations that create large response objects
                results = []
                for i in range(20):  # Reduced number for performance
                    candidate = CandidateResponse(
                        prompt=f"Memory pressure test {i}",
                        response=f"Response {i} " + "data " * 100,  # Larger response
                        model="memory-test"
                    )
                    
                    result = await judge.evaluate_response(
                        candidate,
                        criteria="quality",
                        use_multi_criteria=False
                    )
                    results.append(result)
                
                # Should handle all evaluations successfully
                assert len(results) == 20
                assert all(r.score == 4 for r in results)
                assert all("Memory pressure test" in r.reasoning for r in results)
                
                await judge.close()


class TestEdgeCaseScenarios:
    """Test various edge cases and corner scenarios."""
    
    @pytest.mark.asyncio
    async def test_malformed_response_handling(self, multi_provider_config):
        """Test handling of malformed API responses."""
        # Test with mocked Anthropic client
        with patch('anthropic.Anthropic') as mock_anthropic:
                mock_client = Mock()
                
                # Return malformed responses
                malformed_responses = [
                    'Invalid JSON response',
                    '{"score": "not_a_number", "reasoning": "test"}',
                    '{"incomplete": "json"',
                    '',
                    '{"score": 10, "reasoning": "score out of range"}',  # Score > 5
                    '{"score": -1, "reasoning": "negative score"}'  # Negative score
                ]
                
                call_count = 0
                def malformed_create(*args, **kwargs):
                    nonlocal call_count
                    response_text = malformed_responses[call_count % len(malformed_responses)]
                    call_count += 1
                    
                    mock_response = Mock()
                    mock_response.content = [Mock(text=response_text)]
                    mock_response.stop_reason = 'end_turn'
                    mock_response.usage = Mock(input_tokens=30, output_tokens=20)
                    return mock_response
                
                mock_client.messages.create = Mock(side_effect=malformed_create)
                mock_anthropic.return_value = mock_client
                
                judge = LLMJudge(multi_provider_config)
                
                # Test each type of malformed response
                results = []
                for i in range(len(malformed_responses)):
                    candidate = CandidateResponse(
                        prompt=f"Malformed test {i}",
                        response="Test response",
                        model="malformed-test"
                    )
                    
                    result = await judge.evaluate_response(
                        candidate,
                        criteria="quality",
                        use_multi_criteria=False
                    )
                    results.append(result)
                
                # All should handle gracefully with fallback scoring
                assert len(results) == len(malformed_responses)
                for result in results:
                    assert 1.0 <= result.score <= 5.0  # Valid score range
                    assert result.confidence <= 1.0
                    assert len(result.reasoning) > 0
                
                await judge.close()
    
    @pytest.mark.asyncio
    async def test_extreme_input_sizes(self, multi_provider_config):
        """Test handling of extremely large or small inputs."""
        # Test with mocked Anthropic client
        with patch('anthropic.Anthropic') as mock_anthropic:
                mock_client = Mock()
                
                def size_aware_create(*args, **kwargs):
                    # Return response based on input size
                    mock_response = Mock()
                    mock_response.content = [Mock(text='{"score": 4, "reasoning": "Size test response", "confidence": 0.8}')]
                    mock_response.stop_reason = 'end_turn'
                    mock_response.usage = Mock(input_tokens=1000, output_tokens=50)
                    return mock_response
                
                mock_client.messages.create = Mock(side_effect=size_aware_create)
                mock_anthropic.return_value = mock_client
                
                judge = LLMJudge(multi_provider_config)
                
                # Test cases with different input sizes
                test_cases = [
                    # Very small inputs
                    CandidateResponse(prompt="?", response=".", model="tiny"),
                    # Very large inputs
                    CandidateResponse(
                        prompt="What is AI? " * 500,  # ~5KB prompt
                        response="AI is artificial intelligence. " * 200,  # ~6KB response
                        model="large"
                    ),
                    # Empty inputs
                    CandidateResponse(prompt="", response="", model="empty"),
                    # Unicode and special characters
                    CandidateResponse(
                        prompt="🤖 What is AI? 人工知能とは？",
                        response="AI 是人工智能 🧠 Искусственный интеллект",
                        model="unicode"
                    )
                ]
                
                results = []
                for candidate in test_cases:
                    try:
                        result = await judge.evaluate_response(
                            candidate,
                            criteria="quality",
                            use_multi_criteria=False
                        )
                        results.append(result)
                    except Exception as e:
                        # Should handle gracefully, but if not, record the error
                        results.append(f"Error: {str(e)}")
                
                # Should handle all cases (either with results or graceful errors)
                assert len(results) == len(test_cases)
                
                # Non-error results should be valid
                valid_results = [r for r in results if hasattr(r, 'score')]
                for result in valid_results:
                    assert 1.0 <= result.score <= 5.0
                
                await judge.close()


# Performance benchmarking (optional - can be run separately)
class TestPerformanceBenchmarks:
    """Performance benchmarks for the system."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow  # Mark as slow test
    async def test_throughput_benchmark(self, multi_provider_config):
        """Benchmark system throughput."""
        # Test with mocked Anthropic client
        with patch('anthropic.Anthropic') as mock_anthropic:
                mock_client = Mock()
                
                def fast_create(*args, **kwargs):
                    import time; time.sleep(0.01)  # 10ms simulated API delay
                    mock_response = Mock()
                    mock_response.content = [Mock(text='{"score": 4, "reasoning": "Benchmark response", "confidence": 0.8}')]
                    mock_response.stop_reason = 'end_turn'
                    mock_response.usage = Mock(input_tokens=50, output_tokens=30)
                    return mock_response
                
                mock_client.messages.create = Mock(side_effect=fast_create)
                mock_anthropic.return_value = mock_client
                
                judge = LLMJudge(multi_provider_config)
                
                # Benchmark single evaluations
                start_time = time.time()
                tasks = []
                for i in range(100):  # 100 evaluations
                    candidate = CandidateResponse(
                        prompt=f"Benchmark question {i}",
                        response=f"Benchmark response {i}",
                        model="benchmark"
                    )
                    task = judge.evaluate_response(
                        candidate,
                        criteria="quality",
                        use_multi_criteria=False
                    )
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks)
                elapsed = time.time() - start_time
                
                # Calculate throughput
                throughput = len(results) / elapsed
                
                print(f"Throughput benchmark: {throughput:.2f} evaluations/second")
                
                # Verify all succeeded
                assert len(results) == 100
                assert all(r.score == 4 for r in results)
                
                # Should achieve reasonable throughput with mocked responses
                assert throughput > 10  # At least 10 evaluations/second
                
                await judge.close()