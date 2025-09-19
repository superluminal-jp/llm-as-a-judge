# LLM-as-a-Judge Test Suite Documentation

## Overview

This document provides comprehensive documentation for the LLM-as-a-Judge test suite, explaining the test strategy, architecture, and implementation details.

## Table of Contents

1. [Test Strategy](#test-strategy)
2. [Test Architecture](#test-architecture)
3. [Test Categories](#test-categories)
4. [Test Implementation Details](#test-implementation-details)
5. [Running Tests](#running-tests)
6. [Test Data and Fixtures](#test-data-and-fixtures)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

## Test Strategy

### Philosophy

The test suite follows a **comprehensive testing pyramid** approach with emphasis on:

- **Unit Tests**: Fast, isolated tests for individual components
- **Integration Tests**: End-to-end workflow validation
- **Contract Tests**: API compatibility and interface validation
- **Resilience Tests**: Error handling and fallback mechanisms

### Testing Principles

1. **Test Isolation**: Each test is independent and can run in any order
2. **Deterministic Results**: Tests produce consistent outcomes
3. **Fast Execution**: Unit tests complete in milliseconds
4. **Comprehensive Coverage**: All critical paths and edge cases covered
5. **Realistic Scenarios**: Tests mirror real-world usage patterns

### Quality Gates

- **Test Coverage**: ≥80% line coverage, ≥70% branch coverage
- **Performance**: Unit tests <100ms, integration tests <5s
- **Reliability**: 100% pass rate in CI/CD
- **Maintainability**: Clear test names and documentation

## Test Architecture

### Directory Structure

```
tests/
├── README.md                           # This documentation
├── __init__.py                         # Test package initialization
├── fixtures/                           # Test data and fixtures
│   ├── README.md                       # Fixture documentation
│   └── sample_data/                    # Sample test data
│       ├── minimal_batch.jsonl         # Minimal test cases
│       ├── test_batch.jsonl            # Standard test cases
│       └── sample_batch_results.json   # Expected outputs
├── integration/                        # Integration tests
│   ├── test_bedrock_integration_comprehensive.py
│   ├── test_cli_integration.py
│   ├── test_error_integration.py
│   ├── test_llm_judge_integration.py
│   └── test_timeout_integration.py
└── unit/                              # Unit tests
    ├── application/                    # Application layer tests
    ├── domain/                         # Domain model tests
    ├── infrastructure/                 # Infrastructure tests
    └── presentation/                   # Presentation layer tests
        └── cli/                        # CLI-specific tests
```

### Test Organization

Tests are organized following **Clean Architecture** principles:

- **Domain Tests**: Core business logic and domain models
- **Application Tests**: Use cases and application services
- **Infrastructure Tests**: External dependencies and adapters
- **Presentation Tests**: User interfaces and API endpoints

## Test Categories

### 1. Unit Tests

#### Domain Tests (`tests/unit/domain/`)

**Purpose**: Test core business logic and domain models

**Key Files**:

- `test_evaluation_criteria.py`: Evaluation criteria definitions and validation
- `test_integer_scores.py`: Score handling and integer conversion logic

**Test Coverage**:

- Domain model validation
- Business rule enforcement
- Data integrity checks
- Immutability constraints

**Example Test**:

```python
def test_criterion_definition_validation(self):
    """Test criterion definition validation."""
    with pytest.raises(ValueError, match="scale_min must be less than scale_max"):
        CriterionDefinition(
            name="invalid",
            description="test",
            criterion_type=CriterionType.FACTUAL,
            scale_min=5,
            scale_max=3
        )
```

#### Infrastructure Tests (`tests/unit/infrastructure/`)

**Purpose**: Test external dependencies and infrastructure components

**Key Components**:

- **Client Tests**: LLM provider integrations (OpenAI, Anthropic, Bedrock)
- **Resilience Tests**: Error handling, retry logic, fallback mechanisms
- **Configuration Tests**: Environment setup and validation
- **HTTP Tests**: Network communication and request/response handling

**Client Test Strategy**:

- **Mock-based Tests**: Fast unit tests with mocked dependencies
- **Stubber Tests**: Realistic API simulation using boto3 Stubber
- **Error Scenario Tests**: Comprehensive error handling validation

**Example - Bedrock Client Stubber Test**:

```python
@pytest.mark.asyncio
async def test_invoke_nova_model_success(self, bedrock_client_with_stubber):
    """Test successful Nova model invocation with stubber."""
    client, stubber = bedrock_client_with_stubber

    # Prepare expected request
    expected_request = {
        "modelId": "amazon.nova-pro-v1:0",
        "body": json.dumps({
            "messages": [{"role": "user", "content": [{"text": "Hello Nova!"}]}],
            "inferenceConfig": {"maxTokens": 100, "temperature": 0.1},
        }),
        "contentType": "application/json",
    }

    # Add stub and test
    stubber.add_response("invoke_model", expected_response, expected_request)
    stubber.activate()

    response = await client.invoke_model(messages, max_tokens=100)
    assert response.content == "Hello! I am Nova, Amazon's AI assistant."
```

#### Presentation Tests (`tests/unit/presentation/`)

**Purpose**: Test user interfaces and API endpoints

**Key Files**:

- `test_cli_main.py`: Command-line interface functionality
- `test_config_helper.py`: Configuration management utilities

**Test Coverage**:

- Argument parsing and validation
- Output formatting (JSON, text)
- Error handling and user feedback
- Configuration loading and validation

### 2. Integration Tests

#### LLM Judge Integration (`tests/integration/test_llm_judge_integration.py`)

**Purpose**: End-to-end testing of the core LLM Judge service

**Test Scenarios**:

- **Provider Integration**: OpenAI, Anthropic, Bedrock providers
- **Evaluation Workflows**: Single and multi-criteria evaluation
- **Comparison Workflows**: Response comparison and ranking
- **Fallback Mechanisms**: Error handling and provider switching
- **Resource Management**: Proper cleanup and resource handling

**Example Test**:

```python
@pytest.mark.asyncio
async def test_openai_evaluation_success(self, openai_config):
    """Test successful OpenAI evaluation."""
    judge = LLMJudge(openai_config)

    with patch.object(judge._fallback_manager, "execute_with_fallback") as mock_fallback:
        mock_fallback_response = FallbackResponse(
            content={"score": 4, "reasoning": "Well-structured response", "confidence": 0.9},
            mode=ServiceMode.FULL,
            provider_used="openai",
            confidence=0.9,
            is_cached=False,
        )
        mock_fallback.return_value = mock_fallback_response

        result = await judge.evaluate_response(candidate, "technical accuracy", use_multi_criteria=False)

        assert result.score == 4
        assert "Well-structured response" in result.reasoning
        mock_fallback.assert_called_once()
```

#### Bedrock Integration (`tests/integration/test_bedrock_integration_comprehensive.py`)

**Purpose**: Comprehensive AWS Bedrock integration testing

**Test Coverage**:

- **Model Support**: Nova, Claude models with different configurations
- **Error Handling**: API errors, timeouts, rate limiting
- **Concurrency**: Multiple simultaneous requests
- **Configuration**: Custom parameters and model selection
- **Resource Management**: Proper cleanup and connection handling

#### CLI Integration (`tests/integration/test_cli_integration.py`)

**Purpose**: Command-line interface end-to-end testing

**Test Scenarios**:

- **Command Execution**: Evaluate and compare commands
- **Output Formats**: JSON and text output validation
- **Configuration**: File-based and environment-based config
- **Error Handling**: Invalid arguments and API failures
- **User Experience**: Help display and error messages

#### Error Integration (`tests/integration/test_error_integration.py`)

**Purpose**: System-wide error handling and resilience testing

**Test Coverage**:

- **Error Classification**: Automatic error categorization
- **Retry Logic**: Exponential backoff and retry strategies
- **Logging Integration**: Structured logging and error tracking
- **Real-world Scenarios**: Actual API error patterns

#### Timeout Integration (`tests/integration/test_timeout_integration.py`)

**Purpose**: Timeout management and resource control testing

**Test Coverage**:

- **Timeout Configuration**: Provider-specific timeout settings
- **Operation Cancellation**: Proper timeout handling
- **Resource Cleanup**: Timeout-triggered cleanup procedures

## Test Implementation Details

### Test Fixtures

#### Configuration Fixtures

```python
@pytest.fixture
def openai_config():
    """Create configuration for OpenAI testing."""
    return LLMConfig(
        openai_api_key="test-openai-key",
        default_provider="openai",
        openai_model="gpt-4",
    )
```

#### Client Fixtures

```python
@pytest.fixture
def bedrock_client_with_stubber(test_config):
    """Create a Bedrock client with stubber for testing."""
    with patch("src.llm_judge.infrastructure.clients.bedrock_client.BOTO3_AVAILABLE", True):
        session = boto3.Session(
            aws_access_key_id=test_config.aws_access_key_id,
            aws_secret_access_key=test_config.aws_secret_access_key,
            region_name=test_config.aws_region,
        )
        client = session.client("bedrock-runtime")
        stubber = Stubber(client)

        bedrock_client = BedrockClient(test_config)
        bedrock_client.client = client

        yield bedrock_client, stubber
        stubber.deactivate()
```

### Mocking Strategies

#### 1. Provider Client Mocking

**Purpose**: Isolate tests from external API dependencies

```python
with patch('src.llm_judge.infrastructure.clients.anthropic_client.anthropic.Anthropic') as mock_anthropic_class:
    mock_client = Mock()
    mock_anthropic_class.return_value = mock_client

    # Mock successful response
    mock_response = Mock()
    mock_response.content = [Mock(type="text", text="Test response")]
    mock_client.messages.create.return_value = mock_response
```

#### 2. Fallback Manager Mocking

**Purpose**: Test fallback mechanisms without triggering actual fallbacks

```python
with patch.object(judge._fallback_manager, "execute_with_fallback") as mock_fallback:
    mock_fallback_response = FallbackResponse(
        content={"score": 4, "reasoning": "Test", "confidence": 0.9},
        mode=ServiceMode.FULL,
        provider_used="openai",
        confidence=0.9,
        is_cached=False,
    )
    mock_fallback.return_value = mock_fallback_response
```

#### 3. Stubber-based Testing

**Purpose**: Realistic API simulation with actual request/response validation

```python
# Prepare expected request
expected_request = {
    "modelId": "amazon.nova-pro-v1:0",
    "body": json.dumps({
        "messages": [{"role": "user", "content": [{"text": "Hello Nova!"}]}],
        "inferenceConfig": {"maxTokens": 100, "temperature": 0.1},
    }),
    "contentType": "application/json",
}

# Add stub
stubber.add_response("invoke_model", expected_response, expected_request)
stubber.activate()
```

### Async Testing

All tests involving async operations use `pytest.mark.asyncio`:

```python
@pytest.mark.asyncio
async def test_async_operation(self, fixture):
    """Test async operation."""
    result = await async_function()
    assert result is not None
```

### Error Testing

Comprehensive error scenario testing:

```python
@pytest.mark.asyncio
async def test_throttling_exception(self, bedrock_client_with_stubber):
    """Test handling of throttling exception."""
    client, stubber = bedrock_client_with_stubber

    # Add throttling error stub
    stubber.add_client_error(
        "invoke_model",
        "ThrottlingException",
        "Rate limit exceeded. Please try again later.",
        expected_params=expected_request,
    )
    stubber.activate()

    # Execute test and expect RateLimitError
    with pytest.raises(RateLimitError, match="Rate limit exceeded"):
        await client.invoke_model(messages, max_tokens=100)
```

## Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/llm_judge --cov-report=term-missing --cov-report=html

# Run specific test category
pytest tests/unit/
pytest tests/integration/

# Run specific test file
pytest tests/unit/infrastructure/test_bedrock_client_stubber.py

# Run specific test class
pytest tests/unit/infrastructure/test_bedrock_client_stubber.py::TestBedrockClientStubberNovaModels

# Run specific test method
pytest tests/unit/infrastructure/test_bedrock_client_stubber.py::TestBedrockClientStubberNovaModels::test_invoke_nova_model_success
```

### Test Execution Options

```bash
# Verbose output
pytest -v

# Stop on first failure
pytest -x

# Run tests in parallel
pytest -n auto

# Show local variables on failure
pytest -l

# Run only failed tests from last run
pytest --lf

# Run tests matching pattern
pytest -k "test_bedrock"

# Run tests with specific markers
pytest -m "not slow"
```

### Performance Testing

```bash
# Run with timing information
pytest --durations=10

# Profile slow tests
pytest --profile

# Memory profiling
pytest --memray
```

## Test Data and Fixtures

### Sample Data Files

#### `fixtures/sample_data/minimal_batch.jsonl`

- **Purpose**: Minimal test data for basic functionality
- **Format**: JSONL with `prompt`, `response`, `model` fields
- **Usage**: Quick integration tests and basic validation

#### `fixtures/sample_data/test_batch.jsonl`

- **Purpose**: Standard test scenarios for comprehensive testing
- **Format**: JSONL with various criteria and complexity levels
- **Usage**: Integration tests and batch processing validation

#### `fixtures/sample_data/sample_batch_results.json`

- **Purpose**: Expected batch evaluation output format
- **Format**: JSON with results array and summary statistics
- **Usage**: Output format validation and result parsing tests

### Fixture Usage

```python
def load_test_batch(filename):
    """Load test batch data from fixtures."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "sample_data"
    file_path = fixtures_dir / filename

    with open(file_path, 'r') as f:
        return [json.loads(line) for line in f if line.strip()]

@pytest.fixture
def minimal_test_data():
    return load_test_batch("minimal_batch.jsonl")
```

## Best Practices

### Test Naming

- **Descriptive Names**: Test names should clearly describe what is being tested
- **Given-When-Then**: Use pattern `test_[given]_[when]_[then]`
- **Action-Oriented**: Focus on the behavior being tested

```python
def test_criterion_definition_with_invalid_scale_raises_value_error(self):
    """Test that criterion definition with invalid scale raises ValueError."""

def test_openai_evaluation_with_fallback_returns_mock_result(self):
    """Test that OpenAI evaluation with fallback returns mock result."""
```

### Test Structure

Follow the **AAA Pattern** (Arrange-Act-Assert):

```python
def test_example(self):
    """Test example following AAA pattern."""
    # Arrange
    config = LLMConfig(openai_api_key="test-key")
    client = OpenAIClient(config)

    # Act
    result = client.evaluate("prompt", "response")

    # Assert
    assert result.score >= 1.0
    assert result.score <= 5.0
```

### Error Testing

- **Test Both Success and Failure**: Cover happy path and error scenarios
- **Specific Error Types**: Test for specific exceptions, not generic ones
- **Error Messages**: Validate error messages for debugging

```python
def test_invalid_config_raises_specific_error(self):
    """Test that invalid configuration raises specific error."""
    with pytest.raises(ValueError, match="OpenAI API key is required"):
        LLMConfig(default_provider="openai")  # Missing API key
```

### Async Testing

- **Use `pytest.mark.asyncio`**: For all async test functions
- **Proper Cleanup**: Always clean up resources in async tests
- **Timeout Handling**: Set appropriate timeouts for async operations

```python
@pytest.mark.asyncio
async def test_async_operation(self):
    """Test async operation with proper cleanup."""
    client = AsyncClient()
    try:
        result = await client.operation()
        assert result is not None
    finally:
        await client.close()
```

### Mocking Guidelines

- **Mock at Boundaries**: Mock external dependencies, not internal logic
- **Verify Interactions**: Assert that mocks were called correctly
- **Realistic Responses**: Use realistic mock responses that match real APIs

```python
def test_with_mock_verification(self):
    """Test with proper mock verification."""
    with patch('external_api.call') as mock_call:
        mock_call.return_value = {"status": "success"}

        result = function_under_test()

        # Verify the mock was called correctly
        mock_call.assert_called_once_with(expected_args)
        assert result.status == "success"
```

## Troubleshooting

### Common Issues

#### 1. Import Errors

**Problem**: `ModuleNotFoundError` when running tests

**Solution**: Ensure the project is properly installed and PYTHONPATH is set:

```bash
pip install -e .
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

#### 2. Async Test Failures

**Problem**: Async tests hanging or failing

**Solution**: Ensure proper async/await usage and cleanup:

```python
@pytest.mark.asyncio
async def test_async_with_cleanup(self):
    """Test with proper async cleanup."""
    client = AsyncClient()
    try:
        result = await client.operation()
        assert result is not None
    finally:
        await client.close()
```

#### 3. Mock Not Working

**Problem**: Mocks not being applied correctly

**Solution**: Ensure correct import path and patch location:

```python
# Correct - patch where the object is used, not where it's defined
with patch('src.llm_judge.application.services.llm_judge_service.OpenAIClient') as mock_client:
    # Test code
```

#### 4. Stubber Assertion Errors

**Problem**: `StubAssertionError` in Bedrock tests

**Solution**: Ensure request parameters match exactly:

```python
# Verify request format matches actual client implementation
expected_request = {
    "modelId": "amazon.nova-pro-v1:0",
    "body": json.dumps({
        "messages": [{"role": "user", "content": [{"text": "Hello"}]}],
        "inferenceConfig": {"maxTokens": 100, "temperature": 0.1},
    }),
    "contentType": "application/json",
}
```

### Debugging Tips

#### 1. Verbose Test Output

```bash
pytest -v -s  # Verbose with print statements
pytest --tb=long  # Detailed traceback
pytest --pdb  # Drop into debugger on failure
```

#### 2. Test Isolation

```bash
pytest -x  # Stop on first failure
pytest --lf  # Run only last failed tests
pytest -k "test_name"  # Run specific test
```

#### 3. Coverage Analysis

```bash
pytest --cov=src/llm_judge --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Performance Issues

#### 1. Slow Tests

- Use `pytest --durations=10` to identify slow tests
- Consider using `pytest.mark.slow` for integration tests
- Mock external dependencies in unit tests

#### 2. Memory Issues

- Ensure proper cleanup in async tests
- Use `pytest --memray` for memory profiling
- Check for resource leaks in long-running tests

## Contributing

### Adding New Tests

1. **Follow Naming Conventions**: Use descriptive test names
2. **Add Documentation**: Include docstrings explaining test purpose
3. **Use Appropriate Fixtures**: Leverage existing fixtures or create new ones
4. **Test Edge Cases**: Include boundary conditions and error scenarios
5. **Update Documentation**: Update this README when adding new test categories

### Test Review Checklist

- [ ] Test name clearly describes what is being tested
- [ ] Test follows AAA pattern (Arrange-Act-Assert)
- [ ] Test is isolated and can run independently
- [ ] Test covers both success and failure scenarios
- [ ] Test uses appropriate mocking strategy
- [ ] Test includes proper cleanup for async operations
- [ ] Test documentation is clear and complete

---

## Summary

This test suite provides comprehensive coverage of the LLM-as-a-Judge system, ensuring reliability, performance, and maintainability. The combination of unit tests, integration tests, and realistic API simulation provides confidence in the system's behavior across all scenarios.

For questions or issues with the test suite, please refer to the troubleshooting section or create an issue in the project repository.
