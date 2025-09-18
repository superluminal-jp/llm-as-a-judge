# Bedrock Stubber-Based Tests

This directory contains comprehensive stubber-based tests for the AWS Bedrock client implementation. These tests use boto3's `Stubber` to provide realistic testing without making actual API calls to AWS.

## Overview

The stubber-based tests provide several advantages over traditional mocking:

- **Realistic API Simulation**: Uses actual boto3 client with stubbed responses
- **Request Validation**: Validates that requests are formatted correctly
- **Response Parsing**: Tests actual response parsing logic
- **Error Handling**: Tests real error scenarios with proper exception types
- **Integration Testing**: Tests the full client integration without external dependencies

## Test Files

### `test_bedrock_client_stubber.py`

Comprehensive stubber-based test suite covering:

- **Initialization**: Client setup with AWS credentials
- **Nova Models**: Testing Amazon Nova model interactions
- **Anthropic Models**: Testing Anthropic Claude model interactions
- **Error Scenarios**: Throttling, validation, access denied, and server errors
- **Evaluation**: Multi-criteria evaluation functionality
- **Comparison**: Response comparison functionality
- **Request Validation**: Parameter validation and formatting
- **Integration**: Multiple sequential requests and error recovery

### `test_bedrock_client.py`

Original test file with both mock and stubber approaches.

### `test_bedrock_client_comprehensive.py`

Additional comprehensive tests for edge cases and stress scenarios.

## Key Features

### 1. Realistic Request/Response Testing

```python
# Prepare expected request
expected_request = {
    'modelId': 'amazon.nova-pro-v1:0',
    'body': json.dumps({
        'messages': [{'role': 'user', 'content': 'Hello Nova!'}],
        'max_tokens': 100,
        'inferenceConfig': {
            'temperature': 0.1,
            'topP': 0.9
        }
    }),
    'contentType': 'application/json'
}

# Prepare response
response_body = {
    'output': {
        'message': {
            'content': [{'text': 'Hello! I am Nova.'}]
        }
    },
    'stopReason': 'end_turn',
    'usage': {
        'inputTokens': 10,
        'outputTokens': 20
    }
}

# Add stub and test
stubber.add_response('invoke_model', expected_response, expected_request)
stubber.activate()
```

### 2. Error Scenario Testing

```python
# Test throttling exception
stubber.add_client_error('invoke_model', 'ThrottlingException',
                        'Rate limit exceeded.',
                        expected_params=expected_request)

# Test validation exception
stubber.add_client_error('invoke_model', 'ValidationException',
                        'Invalid request parameters.',
                        expected_params=expected_request)
```

### 3. Model-Specific Testing

The tests cover different model types with their specific request/response formats:

- **Amazon Nova**: Uses `inferenceConfig` and specific response format
- **Anthropic Claude**: Uses `anthropic_version` and different response structure

## Running the Tests

### Using the Test Runner

```bash
# Run all Bedrock tests
python tests/unit/infrastructure/run_bedrock_stubber_tests.py --all

# Run only stubber tests
python tests/unit/infrastructure/run_bedrock_stubber_tests.py --stubber

# Run with verbose output
python tests/unit/infrastructure/run_bedrock_stubber_tests.py --stubber --verbose

# Run with coverage
python tests/unit/infrastructure/run_bedrock_stubber_tests.py --all --coverage
```

### Using pytest directly

```bash
# Run stubber tests
pytest tests/unit/infrastructure/test_bedrock_client_stubber.py -v

# Run specific test class
pytest tests/unit/infrastructure/test_bedrock_client_stubber.py::TestBedrockClientStubberNovaModels -v

# Run with coverage
pytest tests/unit/infrastructure/test_bedrock_client_stubber.py --cov=src.llm_judge.infrastructure.clients.bedrock_client
```

## Test Structure

### Fixtures

- `test_config`: Basic configuration for Nova models
- `anthropic_config`: Configuration for Anthropic models
- `bedrock_client_with_stubber`: Client with stubber for Nova models
- `anthropic_client_with_stubber`: Client with stubber for Anthropic models

### Test Classes

1. **TestBedrockClientStubberInitialization**: Client setup and configuration
2. **TestBedrockClientStubberNovaModels**: Nova model-specific functionality
3. **TestBedrockClientStubberAnthropicModels**: Anthropic model-specific functionality
4. **TestBedrockClientStubberErrorScenarios**: Error handling and recovery
5. **TestBedrockClientStubberEvaluation**: Evaluation functionality
6. **TestBedrockClientStubberComparison**: Comparison functionality
7. **TestBedrockClientStubberRequestValidation**: Request formatting and validation
8. **TestBedrockClientStubberIntegration**: Integration and sequential operations

## Best Practices

### 1. Always Clean Up Stubbers

```python
@pytest.fixture
def bedrock_client_with_stubber(test_config):
    # Setup
    client, stubber = setup_client_and_stubber()

    yield client, stubber

    # Cleanup
    stubber.deactivate()
```

### 2. Validate Request Parameters

```python
# Always specify expected parameters
expected_request = {
    'modelId': 'amazon.nova-pro-v1:0',
    'body': json.dumps(expected_body),
    'contentType': 'application/json'
}

stubber.add_response('invoke_model', expected_response, expected_request)
```

### 3. Test Error Scenarios

```python
# Test different error types
stubber.add_client_error('invoke_model', 'ThrottlingException', 'Rate limit exceeded.')
stubber.add_client_error('invoke_model', 'ValidationException', 'Invalid parameters.')
stubber.add_client_error('invoke_model', 'AccessDeniedException', 'Access denied.')
```

### 4. Mock Retry Logic

```python
# Bypass retry logic for focused testing
with patch.object(client._retry_manager, 'execute_with_retry') as mock_retry:
    async def mock_execute(func, **kwargs):
        return await func()
    mock_retry.side_effect = mock_execute
```

## Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Stubber State

```python
# Verify all stubs were used
stubber.assert_no_pending_responses()

# Check stubber state
print(f"Stubber activated: {stubber.activated}")
print(f"Pending responses: {len(stubber._responses)}")
```

### Common Issues

1. **Stubber not activated**: Call `stubber.activate()` before making requests
2. **Parameter mismatch**: Ensure expected parameters match actual request
3. **Response format**: Verify response format matches model type
4. **Cleanup**: Always call `stubber.deactivate()` in fixture cleanup

## Integration with CI/CD

The stubber tests are designed to run in CI/CD environments without requiring AWS credentials:

```yaml
# GitHub Actions example
- name: Run Bedrock Stubber Tests
  run: |
    python -m pytest tests/unit/infrastructure/test_bedrock_client_stubber.py -v --cov=src.llm_judge.infrastructure.clients.bedrock_client
```

## Performance Considerations

- Stubber tests are faster than real API calls
- No network dependencies
- Deterministic results
- Suitable for parallel execution

## Contributing

When adding new tests:

1. Use appropriate fixtures for your model type
2. Follow the existing test structure
3. Include both success and error scenarios
4. Validate request parameters
5. Test response parsing
6. Add documentation for complex test cases

## Dependencies

- `boto3`: AWS SDK for Python
- `botocore`: Core functionality for boto3
- `pytest`: Testing framework
- `pytest-asyncio`: Async test support
- `pytest-cov`: Coverage reporting (optional)
