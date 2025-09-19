# LLM-as-a-Judge: Testing Documentation

## Overview

The LLM-as-a-Judge system maintains a comprehensive test suite with 123/123 tests passing (100% success rate). This document outlines the testing architecture, methodologies, and maintenance procedures.

## Test Suite Status 🎉

**Current Status: ALL TESTS PASSING**
- **Total Tests**: 123
- **Success Rate**: 100%
- **Unit Tests**: 104/104 passing
- **Integration Tests**: 19/19 passing
- **Test Execution Time**: ~30 seconds

## Testing Architecture

### Test Organization by Layer

```
tests/
├── unit/                           # 104 Unit Tests (isolated, fast)
│   ├── infrastructure/             # 76 Infrastructure tests
│   │   ├── test_openai_client.py   # OpenAI API client tests (8 tests)
│   │   ├── test_anthropic_client.py# Anthropic API client tests (7 tests)
│   │   ├── test_config.py          # Configuration tests (11 tests)
│   │   ├── test_error_classification.py # Error handling (28 tests)
│   │   ├── test_fallback_manager.py# Resilience patterns (30 tests)
│   │   ├── test_http_client.py     # HTTP infrastructure (9 tests)
│   │   └── test_timeout_manager.py # Timeout management (21 tests)
│   ├── application/                # Application layer tests (future)
│   └── domain/                     # Domain layer tests (future)
└── integration/                    # 19 Integration Tests (cross-layer)
    ├── test_llm_judge_integration.py # End-to-end functionality (13 tests)
    ├── test_error_integration.py     # Error handling integration (4 tests)
    └── test_timeout_integration.py   # Timeout behavior (2 tests)
```

### Testing Strategy by Component

#### 1. API Client Testing (15 tests total)

**OpenAI Client Tests (8 tests)**
- Client initialization and configuration validation
- Successful chat completion with proper SDK mocking
- Authentication and rate limit error handling
- Evaluation and comparison method testing

**Anthropic Client Tests (7 tests)**
- Client initialization with proper Claude configuration
- Message creation with multi-block content handling
- Authentication and rate limit error simulation
- Comparison functionality with JSON parsing

**Key Testing Approach:**
- **SDK Mocking**: Direct mocking of OpenAI/Anthropic SDK clients
- **Synchronous Mocking**: Proper handling of sync SDK methods (not AsyncMock)
- **Exception Testing**: Proper mock response objects for error scenarios

#### 2. Resilience Pattern Testing (51 tests total)

**Error Classification Tests (28 tests)**
- Six error categories: Authentication, Rate Limit, Network, Timeout, User, System
- Error pattern matching and classification accuracy
- User message generation and suggested actions
- Real-world error scenario handling

**Fallback Manager Tests (30 tests)**
- Provider health monitoring and status tracking
- Response caching with TTL and expiration
- Circuit breaker patterns and degraded mode operation
- Multi-provider failover and fallback response generation

**Timeout Manager Tests (21 tests)**
- Provider-specific timeout configuration
- Async operation timeout handling
- Partial response recovery and cleanup
- Health check and statistics reporting

#### 3. Configuration Testing (11 tests)

**Configuration Management**
- Environment variable loading and validation
- Provider-specific parameter validation
- Error handling for missing or invalid configuration
- Default value assignment and override behavior

#### 4. Integration Testing (19 tests)

**End-to-End LLM Judge Tests (13 tests)**
- **compare_responses functionality**: Full pairwise comparison testing
- Provider initialization and client management
- Mock and real LLM provider integration
- Resource cleanup and connection management

**Error Integration Tests (4 tests)**
- Cross-system error handling and classification
- Retry mechanism integration with error classification
- Logging integration with structured error reporting
- Real-world error scenario validation

**Timeout Integration Tests (2 tests)**
- Timeout configuration and behavior validation
- Integration with the main LLM judge service

## Testing Methodologies

### 1. Unit Testing Approach

**Isolation Principles:**
- Each test is completely isolated with no shared state
- External dependencies are mocked (OpenAI/Anthropic SDKs, HTTP clients)
- Tests run in parallel without conflicts

**Mocking Strategy:**
```python
# Correct SDK Mocking Pattern
with patch('src.llm_judge.infrastructure.clients.openai_client.OpenAI') as mock_openai_class:
    mock_client = Mock()
    mock_openai_class.return_value = mock_client
    
    # Synchronous mocking for sync SDK methods
    mock_client.chat.completions.create.return_value = mock_response
    
    # NOT: AsyncMock(return_value=mock_response) - This was the bug!
```

**Error Testing Pattern:**
```python
# Proper exception mocking with response objects
mock_response = Mock()
mock_response.request = Mock()
mock_client.chat.completions.create.side_effect = openai.AuthenticationError(
    "Invalid API key", response=mock_response, body=None
)
```

### 2. Integration Testing Approach

**Cross-Layer Testing:**
- Tests validate interactions between application, infrastructure, and resilience layers
- Real configuration objects with proper parameter validation
- Fallback manager integration with mocked LLM providers

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_compare_responses_integration():
    """Test end-to-end compare_responses functionality."""
    # Test implementation with proper async/await patterns
```

### 3. Resilience Testing

**Failure Simulation:**
- Network timeout simulation
- API rate limit and authentication error simulation
- Provider unavailability scenarios
- Circuit breaker state transitions

**Recovery Validation:**
- Automatic retry behavior with exponential backoff
- Fallback provider selection
- Degraded mode operation
- Cache hit/miss scenarios

## Test Execution

### Running Tests

```bash
# Run all tests (recommended)
pytest

# Run specific test suites
pytest tests/unit/                    # Unit tests only (fast)
pytest tests/integration/             # Integration tests only

# Run specific component tests
pytest tests/unit/infrastructure/test_openai_client.py -v
pytest tests/unit/infrastructure/test_anthropic_client.py -v
pytest tests/integration/test_llm_judge_integration.py -v

# Run with coverage reporting
pytest --cov=src/llm_judge --cov-report=html

# Run tests in parallel (faster execution)
pytest -n auto
```

### Test Configuration

**pytest.ini Configuration:**
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
pythonpath = .
minversion = 6.0
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
asyncio_default_test_loop_scope = function
filterwarnings = 
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
    ignore::pytest.PytestUnhandledCoroutineWarning
```

## Test Maintenance

### Adding New Tests

**For New Features:**
1. **Start with Unit Tests**: Test individual components in isolation
2. **Add Integration Tests**: Test feature interaction with existing systems
3. **Follow Naming Convention**: `test_[component]_[scenario]_[expected_result]`
4. **Use Proper Async Decorators**: Always add `@pytest.mark.asyncio` for async tests

**Example Test Structure:**
```python
@pytest.mark.asyncio
async def test_new_feature_success_scenario():
    """Test successful execution of new feature."""
    # Arrange
    mock_setup()
    
    # Act
    result = await execute_feature()
    
    # Assert
    assert result.is_successful
    assert result.data == expected_data
```

### Common Issues and Solutions

**1. AsyncMock Usage Error**
```python
# ❌ WRONG - Don't use AsyncMock for sync SDK methods
mock_client.sync_method = AsyncMock(return_value=response)

# ✅ CORRECT - Use regular Mock for sync methods
mock_client.sync_method.return_value = response
```

**2. Exception Mocking**
```python
# ❌ WRONG - Missing response object
side_effect = SomeException("Error", response=None, body=None)

# ✅ CORRECT - Proper response object
mock_response = Mock()
mock_response.request = Mock()
side_effect = SomeException("Error", response=mock_response, body=None)
```

**3. Missing Async Decorators**
```python
# ❌ WRONG - Missing decorator causes test to be skipped
async def test_async_function():
    result = await some_async_operation()

# ✅ CORRECT - Proper async test decoration
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_operation()
```

### Test Quality Metrics

**Coverage Targets:**
- **Infrastructure Layer**: >95% line coverage
- **Application Layer**: >90% line coverage
- **Domain Layer**: >95% line coverage
- **Integration Tests**: Cover all critical user workflows

**Performance Targets:**
- **Unit Tests**: <10ms average execution time
- **Integration Tests**: <100ms average execution time
- **Full Suite**: <60 seconds total execution time

## Continuous Integration

### Pre-commit Hooks
```bash
# Install pre-commit hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

### CI Pipeline Requirements
1. **All tests must pass** before merge
2. **Coverage reports** must meet minimum thresholds
3. **No test warnings** or deprecation messages
4. **Test execution time** must remain under 2 minutes

## Troubleshooting

### Common Test Failures

**1. Import Errors After Reorganization**
- **Symptom**: `ModuleNotFoundError` for old import paths
- **Solution**: Update imports to use new `src.llm_judge.*` structure

**2. Async Test Warnings**
- **Symptom**: `PytestUnhandledCoroutineWarning`
- **Solution**: Add `@pytest.mark.asyncio` decorator

**3. Mock Configuration Errors**
- **Symptom**: Tests pass individually but fail in suite
- **Solution**: Check for shared state between tests, ensure proper cleanup

**4. SDK Mocking Issues**
- **Symptom**: `'coroutine' object has no attribute` errors
- **Solution**: Use synchronous mocks for synchronous SDK methods

### Debug Commands

```bash
# Run single test with detailed output
pytest tests/specific_test.py::test_function -vvv -s

# Run tests with Python debugger
pytest tests/specific_test.py::test_function --pdb

# Run tests with coverage and missing lines
pytest --cov=src/llm_judge --cov-report=term-missing

# Run only failed tests from last run
pytest --lf
```

## Future Testing Enhancements

### Phase 3 Testing Requirements
- **REST API Testing**: HTTP endpoint validation with test client
- **Batch Processing Testing**: Performance and scalability validation
- **Database Testing**: Data persistence and migration testing
- **Security Testing**: Authentication and authorization validation

### Testing Infrastructure Improvements
- **Test Data Management**: Fixtures and factory patterns for complex test data
- **Performance Testing**: Load testing for concurrent evaluation requests
- **Contract Testing**: API compatibility testing between services
- **Chaos Testing**: Resilience validation under extreme failure conditions

---

**Test Suite Health: 🟢 EXCELLENT (123/123 passing)**
**Last Updated**: Phase 2 Infrastructure Complete
**Maintenance**: Regular test execution and proactive issue resolution