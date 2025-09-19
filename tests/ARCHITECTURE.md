# Test Architecture Documentation

## Overview

This document describes the architectural decisions and patterns used in the LLM-as-a-Judge test suite.

## Test Architecture Principles

### 1. Clean Architecture Alignment

The test suite mirrors the Clean Architecture structure of the main application:

```
tests/
├── unit/
│   ├── domain/           # Domain layer tests
│   ├── application/      # Application layer tests
│   ├── infrastructure/   # Infrastructure layer tests
│   └── presentation/     # Presentation layer tests
└── integration/          # Cross-layer integration tests
```

### 2. Test Pyramid Implementation

```
    /\
   /  \     E2E Tests (Few)
  /____\
 /      \   Integration Tests (Some)
/________\
/          \ Unit Tests (Many)
/____________\
```

- **Unit Tests (70%)**: Fast, isolated, comprehensive coverage
- **Integration Tests (20%)**: Cross-component interaction validation
- **End-to-End Tests (10%)**: Full workflow validation

### 3. Dependency Inversion in Testing

Tests depend on abstractions, not concrete implementations:

```python
# Good - Test against interface
def test_evaluation_service(mock_evaluation_repository):
    service = EvaluationService(mock_evaluation_repository)
    # Test service logic without external dependencies

# Bad - Test against concrete implementation
def test_evaluation_service():
    repository = DatabaseRepository()  # Real database dependency
    service = EvaluationService(repository)
    # Test becomes slow and brittle
```

## Test Categories and Responsibilities

### Unit Tests

#### Domain Tests (`tests/unit/domain/`)

**Responsibility**: Test pure business logic without external dependencies

**Characteristics**:

- No I/O operations
- No external API calls
- Deterministic results
- Fast execution (<10ms per test)

**Example**:

```python
def test_criterion_definition_validation(self):
    """Test business rule: scale_min must be less than scale_max."""
    with pytest.raises(ValueError, match="scale_min must be less than scale_max"):
        CriterionDefinition(
            name="invalid",
            description="test",
            criterion_type=CriterionType.FACTUAL,
            scale_min=5,  # Invalid: greater than scale_max
            scale_max=3
        )
```

#### Application Tests (`tests/unit/application/`)

**Responsibility**: Test use cases and application services

**Characteristics**:

- Mock external dependencies
- Test orchestration logic
- Validate business workflows
- Medium execution time (<100ms per test)

#### Infrastructure Tests (`tests/unit/infrastructure/`)

**Responsibility**: Test external integrations and adapters

**Characteristics**:

- Mock external APIs
- Test data transformation
- Validate error handling
- Test configuration management

**Subcategories**:

1. **Client Tests**: LLM provider integrations

   - Mock-based tests for fast execution
   - Stubber-based tests for realistic API simulation

2. **Resilience Tests**: Error handling and fallback mechanisms

   - Retry logic validation
   - Circuit breaker testing
   - Fallback strategy verification

3. **Configuration Tests**: Environment and config management
   - Environment variable handling
   - Configuration validation
   - Default value testing

#### Presentation Tests (`tests/unit/presentation/`)

**Responsibility**: Test user interfaces and API endpoints

**Characteristics**:

- Mock business logic
- Test input validation
- Test output formatting
- Test user interaction flows

### Integration Tests

#### Cross-Layer Integration (`tests/integration/`)

**Responsibility**: Test interactions between different architectural layers

**Characteristics**:

- Real component interactions
- End-to-end workflows
- External dependency simulation
- Slower execution (<5s per test)

**Types**:

1. **Service Integration**: Application + Infrastructure
2. **API Integration**: Presentation + Application
3. **Provider Integration**: Infrastructure + External APIs
4. **Workflow Integration**: Complete user journeys

## Testing Patterns and Strategies

### 1. Mocking Strategies

#### Boundary Mocking

Mock at architectural boundaries to maintain test isolation:

```python
# Application layer test - mock infrastructure
def test_evaluation_use_case(mock_llm_client, mock_repository):
    use_case = EvaluateResponseUseCase(mock_llm_client, mock_repository)
    result = use_case.execute(request)
    assert result.score >= 1.0

# Infrastructure layer test - mock external APIs
def test_openai_client(mock_http_client):
    client = OpenAIClient(config, mock_http_client)
    response = client.evaluate(prompt, response)
    assert response.score == 4
```

#### Stubber-based Testing

Use boto3 Stubber for realistic AWS API simulation:

```python
def test_bedrock_integration(bedrock_client_with_stubber):
    client, stubber = bedrock_client_with_stubber

    # Prepare realistic request/response
    expected_request = {
        "modelId": "amazon.nova-pro-v1:0",
        "body": json.dumps({
            "messages": [{"role": "user", "content": [{"text": "Hello"}]}],
            "inferenceConfig": {"maxTokens": 100, "temperature": 0.1},
        }),
        "contentType": "application/json",
    }

    stubber.add_response("invoke_model", expected_response, expected_request)
    stubber.activate()

    result = await client.invoke_model(messages)
    assert result.content == "Hello! I am Nova."
```

### 2. Fixture Architecture

#### Hierarchical Fixtures

Create reusable fixtures with clear dependencies:

```python
@pytest.fixture
def base_config():
    """Base configuration for all tests."""
    return {
        "request_timeout": 30,
        "max_retries": 3,
        "log_level": "INFO"
    }

@pytest.fixture
def openai_config(base_config):
    """OpenAI-specific configuration."""
    return LLMConfig(
        openai_api_key="test-key",
        default_provider="openai",
        **base_config
    )

@pytest.fixture
def openai_client(openai_config):
    """OpenAI client with mocked dependencies."""
    with patch('openai.OpenAI') as mock_client:
        yield OpenAIClient(openai_config, mock_client)
```

#### Parametrized Fixtures

Use parametrization for testing multiple scenarios:

```python
@pytest.fixture(params=[
    "amazon.nova-pro-v1:0",
    "anthropic.claude-3-sonnet-20240229-v1:0",
    "anthropic.claude-opus-4-1-20250805-v1:0"
])
def bedrock_model(request):
    """Test with different Bedrock models."""
    return request.param

def test_bedrock_model_support(bedrock_model):
    """Test that all Bedrock models are supported."""
    config = LLMConfig(bedrock_model=bedrock_model)
    client = BedrockClient(config)
    assert client.config.bedrock_model == bedrock_model
```

### 3. Error Testing Patterns

#### Comprehensive Error Coverage

Test all error scenarios systematically:

```python
class TestErrorScenarios:
    """Comprehensive error scenario testing."""

    @pytest.mark.parametrize("error_type,expected_exception", [
        ("ThrottlingException", RateLimitError),
        ("ValidationException", BedrockError),
        ("AccessDeniedException", BedrockError),
        ("InternalServerError", BedrockError),
    ])
    async def test_api_error_handling(self, error_type, expected_exception, client, stubber):
        """Test handling of different API error types."""
        stubber.add_client_error("invoke_model", error_type, "Error message")
        stubber.activate()

        with pytest.raises(expected_exception):
            await client.invoke_model(messages)
```

#### Resilience Testing

Test system behavior under failure conditions:

```python
async def test_fallback_mechanism(self, fallback_manager):
    """Test fallback when primary provider fails."""
    # Mock primary provider failure
    async def failing_operation(provider):
        if provider == "openai":
            raise Exception("OpenAI API error")
        return {"result": "success"}

    result = await fallback_manager.execute_with_fallback(
        failing_operation,
        context={"test": "data"}
    )

    assert result.provider_used != "openai"  # Should fallback to another provider
    assert result.success is True
```

### 4. Async Testing Patterns

#### Proper Async Test Structure

```python
@pytest.mark.asyncio
async def test_async_operation(self):
    """Test async operation with proper resource management."""
    client = AsyncClient()
    try:
        # Arrange
        request = EvaluationRequest(prompt="test", response="test")

        # Act
        result = await client.evaluate(request)

        # Assert
        assert result.score >= 1.0
        assert result.score <= 5.0
    finally:
        # Cleanup
        await client.close()
```

#### Concurrent Testing

Test concurrent operations and race conditions:

```python
@pytest.mark.asyncio
async def test_concurrent_evaluations(self, judge):
    """Test multiple concurrent evaluations."""
    candidates = [
        CandidateResponse(prompt=f"Question {i}", response=f"Response {i}")
        for i in range(5)
    ]

    # Execute concurrent evaluations
    tasks = [
        judge.evaluate_response(candidate, "quality")
        for candidate in candidates
    ]

    results = await asyncio.gather(*tasks)

    # Verify all evaluations completed
    assert len(results) == 5
    for result in results:
        assert result.score >= 1.0
        assert result.score <= 5.0
```

## Test Data Management

### 1. Test Data Strategy

#### Minimal Test Data

Use minimal, focused test data for unit tests:

```python
# Good - Minimal, focused data
def test_score_validation():
    score = CriterionScore("accuracy", 3, "Good", 0.8)
    assert score.score == 3

# Bad - Unnecessary complexity
def test_score_validation():
    complex_data = load_large_test_dataset()  # Overkill for simple validation
    score = CriterionScore("accuracy", 3, "Good", 0.8)
    assert score.score == 3
```

#### Realistic Test Data

Use realistic data for integration tests:

```python
# Integration test with realistic data
def test_evaluation_workflow():
    candidate = CandidateResponse(
        prompt="What is artificial intelligence?",
        response="AI is a field of computer science focused on creating intelligent machines.",
        model="gpt-4"
    )

    result = await judge.evaluate_response(candidate, "accuracy and clarity")
    assert result.score >= 1.0
    assert result.score <= 5.0
```

### 2. Fixture Data Management

#### External Test Data Files

Store complex test data in external files:

```json
// fixtures/sample_data/test_batch.jsonl
{"type": "single", "prompt": "What is AI?", "response": "AI is artificial intelligence", "model": "test-model", "criteria": "accuracy"}
{"type": "single", "prompt": "Explain ML", "response": "Machine learning is a subset of AI", "model": "test-model", "criteria": "clarity"}
```

#### Dynamic Test Data Generation

Generate test data programmatically when needed:

```python
@pytest.fixture
def random_candidate():
    """Generate random candidate response for testing."""
    prompts = ["What is AI?", "Explain ML", "Define NLP"]
    responses = ["AI is artificial intelligence", "ML is machine learning", "NLP is natural language processing"]

    return CandidateResponse(
        prompt=random.choice(prompts),
        response=random.choice(responses),
        model="test-model"
    )
```

## Performance and Scalability

### 1. Test Performance Optimization

#### Fast Unit Tests

- Mock all external dependencies
- Use in-memory data structures
- Avoid I/O operations
- Target <10ms execution time

#### Efficient Integration Tests

- Use realistic but minimal test data
- Mock external APIs with stubbers
- Target <5s execution time
- Run in parallel when possible

### 2. Test Parallelization

#### Parallel Test Execution

```bash
# Run tests in parallel
pytest -n auto

# Run specific test categories in parallel
pytest tests/unit/ -n 4
pytest tests/integration/ -n 2
```

#### Test Isolation for Parallelization

Ensure tests can run in parallel without conflicts:

```python
# Good - Isolated test with unique resources
@pytest.fixture
def isolated_client():
    """Create isolated client for parallel testing."""
    config = LLMConfig(openai_api_key=f"test-key-{uuid.uuid4()}")
    return OpenAIClient(config)

# Bad - Shared global state
GLOBAL_CLIENT = OpenAIClient(shared_config)  # Not safe for parallel execution
```

### 3. Test Scalability

#### Test Suite Growth Management

- Organize tests by feature/component
- Use test discovery patterns
- Implement test categorization
- Monitor test execution time

#### Continuous Integration Optimization

```yaml
# .github/workflows/test.yml
- name: Run Fast Tests
  run: pytest tests/unit/ -n auto

- name: Run Integration Tests
  run: pytest tests/integration/ -n 2

- name: Run Full Test Suite
  run: pytest --cov=src/llm_judge
```

## Quality Assurance

### 1. Test Coverage Requirements

- **Line Coverage**: ≥80%
- **Branch Coverage**: ≥70%
- **Critical Path Coverage**: 100%
- **Error Path Coverage**: 100%

### 2. Test Quality Metrics

- **Test Reliability**: 100% pass rate in CI/CD
- **Test Performance**: Unit tests <10ms, integration tests <5s
- **Test Maintainability**: Clear naming and documentation
- **Test Coverage**: Comprehensive scenario coverage

### 3. Test Review Process

#### Code Review Checklist

- [ ] Test follows AAA pattern (Arrange-Act-Assert)
- [ ] Test is isolated and can run independently
- [ ] Test covers both success and failure scenarios
- [ ] Test uses appropriate mocking strategy
- [ ] Test includes proper cleanup for async operations
- [ ] Test documentation is clear and complete

#### Test Quality Gates

- [ ] All tests pass in CI/CD
- [ ] Test coverage meets requirements
- [ ] Test performance is within limits
- [ ] Test documentation is complete
- [ ] Test follows established patterns

## Conclusion

This test architecture provides a solid foundation for maintaining high-quality, reliable tests that scale with the application. The combination of Clean Architecture alignment, comprehensive testing patterns, and quality assurance processes ensures that the test suite remains maintainable and effective as the system grows.

The key principles are:

1. **Isolation**: Tests should be independent and isolated
2. **Realism**: Tests should reflect real-world usage patterns
3. **Performance**: Tests should be fast and efficient
4. **Maintainability**: Tests should be easy to understand and modify
5. **Coverage**: Tests should provide comprehensive coverage of functionality
