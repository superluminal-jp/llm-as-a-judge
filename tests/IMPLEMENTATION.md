# Test Implementation Guide

## Overview

This document provides detailed implementation guidance for writing, maintaining, and extending tests in the LLM-as-a-Judge test suite.

## Test Implementation Patterns

### 1. Unit Test Implementation

#### Domain Model Tests

**Pattern**: Test pure business logic without external dependencies

```python
class TestCriterionDefinition:
    """Test CriterionDefinition domain model."""

    def test_criterion_definition_creation(self):
        """Test basic criterion definition creation."""
        # Arrange
        criterion = CriterionDefinition(
            name="accuracy",
            description="Factual correctness of the response",
            criterion_type=CriterionType.FACTUAL,
            weight=0.3,
            scale_min=1,
            scale_max=5
        )

        # Act & Assert
        assert criterion.name == "accuracy"
        assert criterion.description == "Factual correctness of the response"
        assert criterion.criterion_type == CriterionType.FACTUAL
        assert criterion.weight == 0.3
        assert criterion.scale_min == 1
        assert criterion.scale_max == 5

    def test_criterion_definition_validation(self):
        """Test criterion definition validation rules."""
        # Test invalid scale
        with pytest.raises(ValueError, match="scale_min must be less than scale_max"):
            CriterionDefinition(
                name="invalid",
                description="test",
                criterion_type=CriterionType.FACTUAL,
                scale_min=5,
                scale_max=3
            )

        # Test negative weight
        with pytest.raises(ValueError, match="Criterion weight must be between 0 and 1"):
            CriterionDefinition(
                name="invalid",
                description="test",
                criterion_type=CriterionType.FACTUAL,
                weight=-0.1
            )
```

**Key Implementation Points**:

- Test business rules and validation logic
- Use descriptive test names that explain the scenario
- Test both valid and invalid inputs
- Focus on domain logic, not infrastructure concerns

#### Application Service Tests

**Pattern**: Test use cases with mocked dependencies

```python
class TestEvaluationService:
    """Test evaluation service use cases."""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM client for testing."""
        with patch('src.llm_judge.infrastructure.clients.openai_client.OpenAIClient') as mock_client:
            mock_response = {
                "score": 4,
                "reasoning": "Well-structured and accurate response",
                "confidence": 0.9
            }
            mock_client.evaluate_with_openai.return_value = mock_response
            yield mock_client

    @pytest.fixture
    def mock_repository(self):
        """Mock repository for testing."""
        with patch('src.llm_judge.infrastructure.repositories.evaluation_repository.EvaluationRepository') as mock_repo:
            yield mock_repo

    @pytest.mark.asyncio
    async def test_evaluate_response_success(self, mock_llm_client, mock_repository):
        """Test successful response evaluation."""
        # Arrange
        service = EvaluationService(mock_llm_client, mock_repository)
        request = EvaluationRequest(
            prompt="What is AI?",
            response="AI is artificial intelligence",
            criteria="accuracy"
        )

        # Act
        result = await service.evaluate_response(request)

        # Assert
        assert result.score == 4
        assert result.reasoning == "Well-structured and accurate response"
        assert result.confidence == 0.9

        # Verify interactions
        mock_llm_client.evaluate_with_openai.assert_called_once_with(
            prompt="What is AI?",
            response="AI is artificial intelligence",
            criteria="accuracy"
        )
        mock_repository.save_evaluation.assert_called_once()
```

**Key Implementation Points**:

- Mock external dependencies at the boundary
- Test the orchestration logic of use cases
- Verify interactions with dependencies
- Test both success and failure scenarios

#### Infrastructure Tests

**Pattern**: Test external integrations with realistic mocking

```python
class TestOpenAIClient:
    """Test OpenAI client integration."""

    @pytest.fixture
    def test_config(self):
        """Create test configuration."""
        return LLMConfig(
            openai_api_key="test-openai-key",
            default_provider="openai",
            openai_model="gpt-4"
        )

    @pytest.mark.asyncio
    async def test_successful_chat_completion(self, test_config):
        """Test successful chat completion."""
        # Arrange
        with patch('openai.OpenAI') as mock_openai:
            mock_response = Mock()
            mock_response.choices = [
                Mock(message=Mock(content='{"score": 4, "reasoning": "Good response", "confidence": 0.8}'))
            ]
            mock_openai.chat.completions.create.return_value = mock_response

            client = OpenAIClient(test_config)

            # Act
            result = await client.evaluate_with_openai(
                prompt="What is AI?",
                response="AI is artificial intelligence",
                criteria="accuracy"
            )

            # Assert
            assert result["score"] == 4
            assert result["reasoning"] == "Good response"
            assert result["confidence"] == 0.8

            # Verify API call
            mock_openai.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_authentication_error(self, test_config):
        """Test handling of authentication errors."""
        # Arrange
        with patch('openai.OpenAI') as mock_openai:
            mock_openai.chat.completions.create.side_effect = openai.AuthenticationError(
                "Invalid API key", response=None, body=None
            )

            client = OpenAIClient(test_config)

            # Act & Assert
            with pytest.raises(OpenAIError, match="Authentication failed"):
                await client.evaluate_with_openai(
                    prompt="What is AI?",
                    response="AI is artificial intelligence",
                    criteria="accuracy"
                )
```

**Key Implementation Points**:

- Mock external APIs at the SDK level
- Test error handling and edge cases
- Verify correct API usage patterns
- Test data transformation and parsing

### 2. Integration Test Implementation

#### Service Integration Tests

**Pattern**: Test interactions between application and infrastructure layers

```python
class TestLLMJudgeIntegration:
    """Test LLM Judge service integration."""

    @pytest.fixture
    def openai_config(self):
        """Create OpenAI configuration."""
        return LLMConfig(
            openai_api_key="test-openai-key",
            default_provider="openai",
            openai_model="gpt-4"
        )

    @pytest.mark.asyncio
    async def test_evaluation_workflow_integration(self, openai_config):
        """Test complete evaluation workflow."""
        # Arrange
        judge = LLMJudge(openai_config)
        candidate = CandidateResponse(
            prompt="What is AI?",
            response="AI is artificial intelligence",
            model="gpt-4"
        )

        # Mock the fallback manager to return successful result
        with patch.object(judge._fallback_manager, "execute_with_fallback") as mock_fallback:
            mock_fallback_response = FallbackResponse(
                content={
                    "score": 4,
                    "reasoning": "Well-structured and accurate response",
                    "confidence": 0.9
                },
                mode=ServiceMode.FULL,
                provider_used="openai",
                confidence=0.9,
                is_cached=False
            )
            mock_fallback.return_value = mock_fallback_response

            # Act
            result = await judge.evaluate_response(
                candidate, "technical accuracy", use_multi_criteria=False
            )

            # Assert
            assert isinstance(result.score, float)
            assert result.score >= 1.0 and result.score <= 5.0
            assert "Well-structured and accurate response" in result.reasoning
            assert isinstance(result.confidence, float)
            assert result.confidence >= 0.0 and result.confidence <= 1.0

            # Verify fallback manager was called
            mock_fallback.assert_called_once()

        # Cleanup
        await judge.close()
```

**Key Implementation Points**:

- Test complete workflows end-to-end
- Use realistic test data and scenarios
- Mock external dependencies appropriately
- Verify proper resource cleanup

#### API Integration Tests

**Pattern**: Test API endpoints with realistic request/response cycles

```python
class TestCLIIntegration:
    """Test CLI integration scenarios."""

    @pytest.mark.asyncio
    async def test_cli_evaluate_with_mock_judge(self):
        """Test CLI evaluation command with mocked LLM judge."""
        # Arrange
        test_args = [
            '--output', 'json',
            'evaluate',
            'What is artificial intelligence?',
            'AI is a field of computer science that aims to create intelligent machines.',
            '--criteria', 'accuracy'
        ]

        mock_criteria_result = MultiCriteriaResult(
            criterion_scores=[
                CriterionScore('accuracy', 5, 'Excellent accuracy', 0.9),
                CriterionScore('clarity', 4, 'Good clarity', 0.8)
            ],
            judge_model='gpt-4'
        )

        # Act
        with patch('src.llm_judge.presentation.cli.main.LLMJudge') as mock_judge_class, \
             patch('sys.argv', ['llm-judge'] + test_args):

            mock_judge = AsyncMock()
            mock_judge.evaluate_multi_criteria.return_value = mock_criteria_result
            mock_judge.judge_model = 'gpt-4'
            mock_judge.close = AsyncMock()
            mock_judge_class.return_value = mock_judge

            with patch('builtins.print') as mock_print:
                await main()

                # Assert
                mock_judge.evaluate_multi_criteria.assert_called_once()
                mock_judge.close.assert_called_once()

                # Check that JSON output was printed
                mock_print.assert_called()
                call_args = mock_print.call_args[0][0]
                assert '"type": "multi_criteria_evaluation"' in call_args
```

**Key Implementation Points**:

- Test complete user workflows
- Mock external dependencies at appropriate boundaries
- Verify correct output formatting
- Test error handling and edge cases

### 3. Stubber-Based Testing Implementation

**Pattern**: Use boto3 Stubber for realistic AWS API simulation

```python
class TestBedrockClientStubber:
    """Test Bedrock client using boto3 Stubber."""

    @pytest.fixture
    def bedrock_client_with_stubber(self, test_config):
        """Create a Bedrock client with stubber for testing."""
        with patch("src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True):
            # Create real boto3 session and client for stubbing
            session = boto3.Session(
                aws_access_key_id=test_config.aws_access_key_id,
                aws_secret_access_key=test_config.aws_secret_access_key,
                region_name=test_config.aws_region,
            )
            client = session.client("bedrock-runtime")
            stubber = Stubber(client)

            # Create BedrockClient with the real client
            bedrock_client = BedrockClient(test_config)
            bedrock_client.client = client  # Replace with stubbed client

            yield bedrock_client, stubber

            # Clean up
            stubber.deactivate()

    @pytest.mark.asyncio
    async def test_invoke_nova_model_success(self, bedrock_client_with_stubber):
        """Test successful Nova model invocation with stubber."""
        client, stubber = bedrock_client_with_stubber

        # Prepare expected request
        expected_request = {
            "modelId": "amazon.nova-pro-v1:0",
            "body": json.dumps({
                "messages": [
                    {"role": "user", "content": [{"text": "Hello Nova!"}]}
                ],
                "inferenceConfig": {"maxTokens": 100, "temperature": 0.1},
            }),
            "contentType": "application/json",
        }

        # Prepare successful response
        response_body = {
            "output": {
                "message": {
                    "content": [{"text": "Hello! I am Nova, Amazon's AI assistant."}]
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 10, "outputTokens": 20},
        }

        expected_response = {"body": Mock(), "contentType": "application/json"}
        expected_response["body"].read.return_value = json.dumps(response_body).encode("utf-8")

        # Add stub
        stubber.add_response("invoke_model", expected_response, expected_request)
        stubber.activate()

        # Mock retry manager to bypass retry logic
        with patch.object(client._retry_manager, "execute_with_retry") as mock_retry:
            async def mock_execute(func, **kwargs):
                return await func()
            mock_retry.side_effect = mock_execute

            # Execute test
            messages = [{"role": "user", "content": "Hello Nova!"}]
            response = await client.invoke_model(messages, max_tokens=100)

            # Verify response
            assert isinstance(response, BedrockResponse)
            assert response.content == "Hello! I am Nova, Amazon's AI assistant."
            assert response.model == "amazon.nova-pro-v1:0"
            assert response.stop_reason == "end_turn"
            assert response.usage["input_tokens"] == 10
            assert response.usage["output_tokens"] == 20

        # Verify stub was called correctly
        stubber.assert_no_pending_responses()
```

**Key Implementation Points**:

- Use real boto3 client with stubbed responses
- Prepare realistic request/response pairs
- Test actual API usage patterns
- Verify proper stub cleanup

## Test Fixture Implementation

### 1. Configuration Fixtures

```python
@pytest.fixture
def base_config():
    """Base configuration for all tests."""
    return {
        "request_timeout": 30,
        "max_retries": 3,
        "retry_delay": 1,
        "log_level": "INFO"
    }

@pytest.fixture
def openai_config(base_config):
    """OpenAI-specific configuration."""
    return LLMConfig(
        openai_api_key="test-openai-key",
        default_provider="openai",
        openai_model="gpt-4",
        **base_config
    )

@pytest.fixture
def anthropic_config(base_config):
    """Anthropic-specific configuration."""
    return LLMConfig(
        anthropic_api_key="test-anthropic-key",
        default_provider="anthropic",
        anthropic_model="claude-sonnet-4-20250514",
        **base_config
    )

@pytest.fixture
def bedrock_config(base_config):
    """Bedrock-specific configuration."""
    return LLMConfig(
        aws_access_key_id="AKIATEST123456789",
        aws_secret_access_key="test-secret-access-key-12345",
        aws_region="us-east-1",
        bedrock_model="amazon.nova-pro-v1:0",
        default_provider="bedrock",
        **base_config
    )
```

### 2. Client Fixtures

```python
@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    with patch('openai.OpenAI') as mock_client:
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content='{"score": 4, "reasoning": "Good response", "confidence": 0.8}'))
        ]
        mock_client.chat.completions.create.return_value = mock_response
        yield mock_client

@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing."""
    with patch('anthropic.Anthropic') as mock_client:
        mock_response = Mock()
        mock_response.content = [Mock(type="text", text='{"score": 4, "reasoning": "Good response", "confidence": 0.8}')]
        mock_response.stop_reason = "end_turn"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 8
        mock_client.messages.create.return_value = mock_response
        yield mock_client
```

### 3. Data Fixtures

```python
@pytest.fixture
def sample_candidate():
    """Create sample candidate response for testing."""
    return CandidateResponse(
        prompt="What is artificial intelligence?",
        response="AI is a field of computer science that aims to create machines that mimic human intelligence.",
        model="test-model"
    )

@pytest.fixture
def sample_candidates():
    """Create multiple sample candidates for testing."""
    return [
        CandidateResponse(
            prompt="What is AI?",
            response="AI is artificial intelligence",
            model="model-a"
        ),
        CandidateResponse(
            prompt="What is AI?",
            response="AI is a field of computer science focused on creating intelligent machines",
            model="model-b"
        )
    ]

@pytest.fixture
def evaluation_criteria():
    """Create evaluation criteria for testing."""
    return DefaultCriteria.comprehensive()
```

### 4. Mock Response Fixtures

```python
@pytest.fixture
def mock_evaluation_response():
    """Mock evaluation response."""
    return {
        "score": 4,
        "reasoning": "Well-structured and accurate response",
        "confidence": 0.9
    }

@pytest.fixture
def mock_comparison_response():
    """Mock comparison response."""
    return {
        "winner": "A",
        "reasoning": "Response A is more comprehensive",
        "confidence": 0.8
    }

@pytest.fixture
def mock_multi_criteria_response():
    """Mock multi-criteria evaluation response."""
    return MultiCriteriaResult(
        criterion_scores=[
            CriterionScore("accuracy", 4, "Good accuracy", 0.9),
            CriterionScore("clarity", 3, "Fair clarity", 0.8),
            CriterionScore("completeness", 4, "Good completeness", 0.85)
        ],
        judge_model="gpt-4"
    )
```

## Error Testing Implementation

### 1. Exception Testing

```python
def test_invalid_config_raises_error():
    """Test that invalid configuration raises appropriate error."""
    with pytest.raises(ValueError, match="OpenAI API key is required"):
        LLMConfig(default_provider="openai")  # Missing API key

def test_invalid_score_raises_error():
    """Test that invalid score raises appropriate error."""
    with pytest.raises(ValueError, match="Score must be between 1 and 5"):
        CriterionScore("accuracy", 6, "Invalid score", 0.8)
```

### 2. API Error Testing

```python
@pytest.mark.asyncio
async def test_openai_authentication_error(self, test_config):
    """Test handling of OpenAI authentication errors."""
    with patch('openai.OpenAI') as mock_openai:
        mock_openai.chat.completions.create.side_effect = openai.AuthenticationError(
            "Invalid API key", response=None, body=None
        )

        client = OpenAIClient(test_config)

        with pytest.raises(OpenAIError, match="Authentication failed"):
            await client.evaluate_with_openai(
                prompt="What is AI?",
                response="AI is artificial intelligence",
                criteria="accuracy"
            )

@pytest.mark.asyncio
async def test_rate_limit_error(self, test_config):
    """Test handling of rate limit errors."""
    with patch('openai.OpenAI') as mock_openai:
        mock_openai.chat.completions.create.side_effect = openai.RateLimitError(
            "Rate limit exceeded", response=None, body=None
        )

        client = OpenAIClient(test_config)

        with pytest.raises(RateLimitError, match="Rate limit exceeded"):
            await client.evaluate_with_openai(
                prompt="What is AI?",
                response="AI is artificial intelligence",
                criteria="accuracy"
            )
```

### 3. Fallback Testing

```python
@pytest.mark.asyncio
async def test_fallback_mechanism(self, fallback_manager):
    """Test fallback when primary provider fails."""
    # Mock operation that fails for first provider
    async def mock_operation(provider):
        if provider == "openai":
            raise Exception("OpenAI API error")
        return {"result": "success", "provider": provider}

    result = await fallback_manager.execute_with_fallback(
        mock_operation,
        context={"test": "data"}
    )

    # Should fallback to another provider
    assert result.provider_used != "openai"
    assert result.success is True
    assert result.content["result"] == "success"
```

## Performance Testing Implementation

### 1. Execution Time Testing

```python
@pytest.mark.performance
def test_evaluation_performance():
    """Test that evaluation completes within performance requirements."""
    start_time = time.time()

    result = await judge.evaluate_response(candidate, "accuracy")

    execution_time = time.time() - start_time
    assert execution_time < 2.0  # Should complete within 2 seconds

@pytest.mark.performance
def test_concurrent_evaluations_performance():
    """Test performance of concurrent evaluations."""
    start_time = time.time()

    # Create multiple concurrent evaluations
    tasks = [
        judge.evaluate_response(candidate, "accuracy")
        for _ in range(10)
    ]

    results = await asyncio.gather(*tasks)

    execution_time = time.time() - start_time
    assert execution_time < 10.0  # Should complete within 10 seconds
    assert len(results) == 10
```

### 2. Memory Usage Testing

```python
@pytest.mark.performance
def test_memory_usage():
    """Test memory usage during evaluation."""
    import psutil
    import os

    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss

    # Perform evaluation
    result = await judge.evaluate_response(candidate, "accuracy")

    final_memory = process.memory_info().rss
    memory_increase = final_memory - initial_memory

    # Memory increase should be reasonable (less than 10MB)
    assert memory_increase < 10 * 1024 * 1024
```

## Test Data Management

### 1. External Test Data

```python
def load_test_batch(filename):
    """Load test batch data from fixtures."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "sample_data"
    file_path = fixtures_dir / filename

    with open(file_path, 'r') as f:
        return [json.loads(line) for line in f if line.strip()]

@pytest.fixture
def minimal_test_data():
    """Load minimal test data."""
    return load_test_batch("minimal_batch.jsonl")

@pytest.fixture
def standard_test_data():
    """Load standard test data."""
    return load_test_batch("test_batch.jsonl")
```

### 2. Dynamic Test Data

```python
@pytest.fixture
def random_candidate():
    """Generate random candidate response for testing."""
    prompts = [
        "What is artificial intelligence?",
        "Explain machine learning",
        "Define natural language processing",
        "What is deep learning?",
        "Explain neural networks"
    ]

    responses = [
        "AI is artificial intelligence",
        "ML is machine learning",
        "NLP is natural language processing",
        "Deep learning is a subset of ML",
        "Neural networks are computing systems"
    ]

    return CandidateResponse(
        prompt=random.choice(prompts),
        response=random.choice(responses),
        model="test-model"
    )

@pytest.fixture
def parametrized_candidates():
    """Generate candidates for parametrized testing."""
    test_cases = [
        ("What is AI?", "AI is artificial intelligence", "accuracy"),
        ("Explain ML", "ML is machine learning", "clarity"),
        ("Define NLP", "NLP is natural language processing", "completeness")
    ]

    return [
        CandidateResponse(prompt=prompt, response=response, model="test-model")
        for prompt, response, _ in test_cases
    ]
```

## Test Utilities

### 1. Assertion Helpers

```python
def assert_valid_evaluation_result(result):
    """Assert that evaluation result is valid."""
    assert isinstance(result.score, (int, float))
    assert 1.0 <= result.score <= 5.0
    assert isinstance(result.reasoning, str)
    assert len(result.reasoning) > 0
    assert isinstance(result.confidence, (int, float))
    assert 0.0 <= result.confidence <= 1.0

def assert_valid_comparison_result(result):
    """Assert that comparison result is valid."""
    assert isinstance(result, dict)
    assert "winner" in result
    assert result["winner"] in ["A", "B", "tie"]
    assert "reasoning" in result
    assert isinstance(result["reasoning"], str)
    assert len(result["reasoning"]) > 0
    assert "confidence" in result
    assert 0.0 <= result["confidence"] <= 1.0

def assert_valid_multi_criteria_result(result):
    """Assert that multi-criteria result is valid."""
    assert isinstance(result, MultiCriteriaResult)
    assert len(result.criterion_scores) > 0
    assert result.aggregated is not None
    assert 1.0 <= result.aggregated.overall_score <= 5.0

    for score in result.criterion_scores:
        assert 1.0 <= score.score <= 5.0
        assert isinstance(score.reasoning, str)
        assert len(score.reasoning) > 0
        assert 0.0 <= score.confidence <= 1.0
```

### 2. Mock Helpers

```python
def create_mock_openai_response(score=4, reasoning="Test reasoning", confidence=0.8):
    """Create mock OpenAI response."""
    return {
        "score": score,
        "reasoning": reasoning,
        "confidence": confidence
    }

def create_mock_anthropic_response(score=4, reasoning="Test reasoning", confidence=0.8):
    """Create mock Anthropic response."""
    return {
        "score": score,
        "reasoning": reasoning,
        "confidence": confidence
    }

def create_mock_bedrock_response(score=4, reasoning="Test reasoning", confidence=0.8):
    """Create mock Bedrock response."""
    return {
        "score": score,
        "reasoning": reasoning,
        "confidence": confidence
    }
```

### 3. Test Data Generators

```python
def generate_test_candidates(count=5):
    """Generate multiple test candidates."""
    prompts = [
        "What is artificial intelligence?",
        "Explain machine learning",
        "Define natural language processing",
        "What is deep learning?",
        "Explain neural networks"
    ]

    responses = [
        "AI is artificial intelligence",
        "ML is machine learning",
        "NLP is natural language processing",
        "Deep learning is a subset of ML",
        "Neural networks are computing systems"
    ]

    return [
        CandidateResponse(
            prompt=prompts[i % len(prompts)],
            response=responses[i % len(responses)],
            model=f"test-model-{i}"
        )
        for i in range(count)
    ]

def generate_test_configs():
    """Generate test configurations for different providers."""
    return {
        "openai": LLMConfig(
            openai_api_key="test-openai-key",
            default_provider="openai",
            openai_model="gpt-4"
        ),
        "anthropic": LLMConfig(
            anthropic_api_key="test-anthropic-key",
            default_provider="anthropic",
            anthropic_model="claude-sonnet-4-20250514"
        ),
        "bedrock": LLMConfig(
            aws_access_key_id="AKIATEST123456789",
            aws_secret_access_key="test-secret-access-key-12345",
            aws_region="us-east-1",
            bedrock_model="amazon.nova-pro-v1:0",
            default_provider="bedrock"
        )
    }
```

## Best Practices Summary

### 1. Test Structure

- **AAA Pattern**: Arrange-Act-Assert
- **Single Responsibility**: One test, one behavior
- **Descriptive Names**: Clear test names that explain the scenario
- **Proper Documentation**: Docstrings explaining test purpose

### 2. Mocking Strategy

- **Mock at Boundaries**: Mock external dependencies, not internal logic
- **Verify Interactions**: Assert that mocks were called correctly
- **Realistic Responses**: Use realistic mock responses
- **Proper Cleanup**: Clean up mocks and resources

### 3. Error Testing

- **Test Both Success and Failure**: Cover happy path and error scenarios
- **Specific Error Types**: Test for specific exceptions
- **Error Messages**: Validate error messages for debugging
- **Edge Cases**: Test boundary conditions and edge cases

### 4. Performance Testing

- **Execution Time**: Test that operations complete within time limits
- **Memory Usage**: Monitor memory consumption
- **Concurrent Operations**: Test concurrent execution
- **Resource Cleanup**: Ensure proper resource cleanup

### 5. Test Data

- **Minimal Data**: Use minimal data for unit tests
- **Realistic Data**: Use realistic data for integration tests
- **External Files**: Store complex data in external files
- **Dynamic Generation**: Generate data programmatically when needed

This implementation guide provides the foundation for writing high-quality, maintainable tests that ensure the reliability and correctness of the LLM-as-a-Judge system.
