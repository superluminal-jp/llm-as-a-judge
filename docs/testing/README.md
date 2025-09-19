# Testing Guide

This guide covers testing strategies, procedures, and best practices for the LLM-as-a-Judge system.

## 🧪 Testing Overview

The LLM-as-a-Judge system includes a comprehensive test suite with 236+ tests covering all layers of the architecture.

### Test Statistics

- **Total Tests**: 236+ tests
- **Unit Tests**: 200+ tests
- **Integration Tests**: 36+ tests
- **Success Rate**: 100% (all tests passing)
- **Coverage**: Comprehensive coverage across all components

## 🏗️ Test Architecture

### Test Organization

```
tests/
├── unit/                       # Unit Tests (isolated, fast)
│   ├── domain/                 # Domain layer tests
│   ├── application/            # Application layer tests
│   ├── infrastructure/         # Infrastructure layer tests
│   └── presentation/           # Presentation layer tests
├── integration/                # Integration Tests (cross-layer)
│   ├── test_llm_judge_integration.py
│   ├── test_error_integration.py
│   └── test_timeout_integration.py
└── fixtures/                   # Test fixtures and sample data
    ├── sample_data/            # Sample data for testing
    └── README.md              # Test fixtures documentation
```

### Testing Strategy by Layer

#### Domain Layer Testing

- **Business Logic**: Test domain models and business rules
- **Validation**: Test input validation and constraints
- **Domain Services**: Test domain service implementations

#### Application Layer Testing

- **Use Cases**: Test application use cases
- **Orchestration**: Test service orchestration
- **Error Handling**: Test application-level error handling

#### Infrastructure Layer Testing

- **API Clients**: Test LLM provider integrations
- **Configuration**: Test configuration loading and validation
- **Resilience**: Test retry, fallback, and circuit breaker patterns
- **Persistence**: Test data storage and retrieval

#### Presentation Layer Testing

- **CLI Interface**: Test command-line interface
- **Input Validation**: Test user input validation
- **Output Formatting**: Test result formatting

## 🚀 Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/infrastructure/test_anthropic_client.py

# Run tests matching pattern
pytest -k "test_anthropic"
```

### Test Suites

```bash
# Run unit tests only
pytest tests/unit/

# Run integration tests only
pytest tests/integration/

# Run domain layer tests
pytest tests/unit/domain/

# Run infrastructure layer tests
pytest tests/unit/infrastructure/
```

### Coverage Analysis

```bash
# Run tests with coverage
pytest --cov=src/llm_judge

# Generate HTML coverage report
pytest --cov=src/llm_judge --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Performance Testing

```bash
# Run performance tests
pytest tests/performance/

# Run with timing information
pytest --durations=10
```

## 🔧 Test Configuration

### Pytest Configuration

The project uses `pytest.ini` for configuration:

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --strict-markers
    --strict-config
    --verbose
    --tb=short
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow running tests
    performance: Performance tests
```

### Test Environment

```bash
# Set test environment variables
export TEST_ENV=true
export LOG_LEVEL=DEBUG

# Run tests with environment
pytest
```

## 📝 Writing Tests

### Test Structure

Follow the AAA pattern (Arrange, Act, Assert):

```python
def test_evaluation_accuracy():
    # Arrange
    judge = LLMJudge()
    candidate = CandidateResponse("What is AI?", "AI is artificial intelligence", "gpt-4")

    # Act
    result = await judge.evaluate_multi_criteria(candidate)

    # Assert
    assert result.aggregated.overall_score >= 1.0
    assert result.aggregated.overall_score <= 5.0
    assert len(result.criterion_scores) == 7
```

### Test Fixtures

Use pytest fixtures for common test setup:

```python
@pytest.fixture
def sample_candidate():
    return CandidateResponse(
        prompt="What is AI?",
        response="AI is artificial intelligence",
        model="gpt-4"
    )

@pytest.fixture
def mock_judge():
    return LLMJudge(config=test_config)

def test_evaluation_with_fixtures(sample_candidate, mock_judge):
    result = await mock_judge.evaluate_multi_criteria(sample_candidate)
    assert result is not None
```

### Async Testing

Use `pytest-asyncio` for async tests:

```python
@pytest.mark.asyncio
async def test_async_evaluation():
    judge = LLMJudge()
    candidate = CandidateResponse("Q", "A", "model")

    result = await judge.evaluate_multi_criteria(candidate)
    assert result.aggregated.overall_score > 0
```

### Mocking External Dependencies

Mock external services for unit tests:

```python
from unittest.mock import AsyncMock, patch

@patch('src.llm_judge.infrastructure.clients.anthropic_client.AnthropicClient')
async def test_anthropic_client_mock(mock_client):
    # Setup mock
    mock_client.return_value.generate_evaluation = AsyncMock(
        return_value={"score": 4.0, "reasoning": "Good response"}
    )

    # Test
    client = AnthropicClient("test-key")
    result = await client.generate_evaluation("test prompt")

    # Assert
    assert result["score"] == 4.0
```

## 🧪 Test Types

### Unit Tests

Test individual components in isolation:

```python
def test_criterion_score_validation():
    # Test domain model validation
    score = CriterionScore(
        criterion_name="accuracy",
        score=4.0,
        reasoning="Good accuracy",
        confidence=0.9
    )

    assert score.score >= 1.0
    assert score.score <= 5.0
    assert score.confidence >= 0.0
    assert score.confidence <= 1.0
```

### Integration Tests

Test component interactions:

```python
@pytest.mark.integration
async def test_llm_judge_integration():
    # Test end-to-end evaluation
    judge = LLMJudge()
    candidate = CandidateResponse("Q", "A", "model")

    result = await judge.evaluate_multi_criteria(candidate)

    assert result.aggregated.overall_score > 0
    assert len(result.criterion_scores) > 0
    assert result.overall_reasoning is not None
```

### Error Testing

Test error scenarios:

```python
async def test_invalid_api_key():
    config = LLMConfig(anthropic_api_key="invalid-key")
    judge = LLMJudge(config=config)

    with pytest.raises(AuthenticationError):
        await judge.evaluate_multi_criteria(candidate)
```

## 🔍 Test Debugging

### Debugging Failed Tests

```bash
# Run specific failing test with debug output
pytest tests/unit/test_specific.py::test_function -v -s

# Run with pdb debugger
pytest --pdb tests/unit/test_specific.py

# Run with detailed traceback
pytest --tb=long tests/unit/test_specific.py
```

### Test Logging

```python
import logging

def test_with_logging(caplog):
    with caplog.at_level(logging.INFO):
        # Your test code
        pass

    assert "Expected log message" in caplog.text
```

## 📊 Test Metrics

### Coverage Metrics

- **Line Coverage**: 90%+ target
- **Branch Coverage**: 85%+ target
- **Function Coverage**: 95%+ target
- **Class Coverage**: 90%+ target

### Performance Metrics

- **Unit Test Speed**: < 1 second per test
- **Integration Test Speed**: < 10 seconds per test
- **Total Test Suite**: < 5 minutes

## 🚀 Continuous Integration

### GitHub Actions

The project uses GitHub Actions for CI:

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest
      - name: Run coverage
        run: pytest --cov=src/llm_judge --cov-report=xml
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

## 🆘 Troubleshooting

### Common Test Issues

1. **Async Test Failures**: Ensure `@pytest.mark.asyncio` decorator
2. **Mock Issues**: Check mock setup and return values
3. **Environment Issues**: Verify test environment variables
4. **Import Errors**: Check Python path and imports

### Test Environment Issues

```bash
# Check Python version
python --version

# Check installed packages
pip list

# Check test configuration
pytest --collect-only
```

## 📚 Related Documentation

- **[Running Tests](running-tests.md)** - Detailed test execution guide
- **[Writing Tests](writing-tests.md)** - Test writing best practices
- **[Test Fixtures](fixtures/README.md)** - Test fixtures and sample data
- **[API Reference](../api/README.md)** - Complete API documentation

## 🎯 Test Goals

### Quality Goals

- **Reliability**: 100% test success rate
- **Coverage**: Comprehensive test coverage
- **Speed**: Fast test execution
- **Maintainability**: Easy to maintain and extend

### Testing Best Practices

- **Test Isolation**: Each test should be independent
- **Clear Assertions**: Use clear, specific assertions
- **Descriptive Names**: Use descriptive test names
- **Documentation**: Document complex test scenarios

---

**Ready to run tests?** Check out the [Running Tests Guide](running-tests.md)!
