# Test Execution Guide - LLM-as-a-Judge System

## Overview

This guide provides comprehensive instructions for executing the LLM-as-a-Judge test suite, including setup, execution commands, troubleshooting, and best practices.

## Quick Start

### Prerequisites Check
```bash
# Verify Python version (3.8+)
python --version

# Check pytest installation
pytest --version

# Verify project structure
ls -la tests/
```

### Basic Test Execution
```bash
# Run working tests (recommended first)
python -m pytest tests/unit/infrastructure/test_fallback_manager_enhanced.py::TestFallbackManagerInitialization -v

# Run all enhanced tests
python -m pytest tests/ -k "enhanced or comprehensive" -v --tb=short
```

## Test Categories and Execution Commands

### 1. Unit Tests

#### Fallback Manager Tests (✅ Working)
```bash
# All fallback manager tests
python -m pytest tests/unit/infrastructure/test_fallback_manager_enhanced.py -v

# Specific test classes
python -m pytest tests/unit/infrastructure/test_fallback_manager_enhanced.py::TestFallbackManagerInitialization -v
python -m pytest tests/unit/infrastructure/test_fallback_manager_enhanced.py::TestHealthMonitor -v
python -m pytest tests/unit/infrastructure/test_fallback_manager_enhanced.py::TestResponseCache -v
```

#### Bedrock Client Tests (⚠️ Mock Issues)
```bash
# Comprehensive Bedrock tests (may have mocking issues)
python -m pytest tests/unit/infrastructure/test_bedrock_client_comprehensive.py -v --tb=short

# Run with detailed error info for debugging
python -m pytest tests/unit/infrastructure/test_bedrock_client_comprehensive.py::TestBedrockClientInitialization::test_missing_boto3_dependency -v -s
```

### 2. Integration Tests

#### Basic Integration Tests
```bash
# All integration tests
python -m pytest tests/integration/ -v

# Bedrock integration (may require mock fixes)
python -m pytest tests/integration/test_bedrock_integration_comprehensive.py -v --tb=short

# Error scenarios (comprehensive but slower)
python -m pytest tests/integration/test_error_scenarios_stress.py::TestNetworkFailureScenarios -v
```

### 3. Stress and Performance Tests

#### High-Load Tests
```bash
# Concurrency stress tests
python -m pytest tests/integration/test_error_scenarios_stress.py::TestConcurrencyStressTests -v

# Performance benchmarks (marked as slow)
python -m pytest tests/integration/test_error_scenarios_stress.py::TestPerformanceBenchmarks -v -m slow
```

## Test Execution Strategies

### 1. Development Workflow

#### Quick Validation (< 1 minute)
```bash
# Essential functionality check
python -m pytest tests/unit/infrastructure/test_fallback_manager_enhanced.py::TestFallbackManagerInitialization::test_fallback_manager_initialization -v
python -m pytest tests/unit/infrastructure/test_fallback_manager_enhanced.py::TestHealthMonitor::test_record_success -v
```

#### Feature Development (2-5 minutes)
```bash
# Test specific component being developed
python -m pytest tests/unit/infrastructure/test_fallback_manager_enhanced.py -v
python -m pytest tests/integration/test_bedrock_integration_comprehensive.py::TestBedrockIntegrationBasic -v
```

#### Pre-Commit Validation (5-10 minutes)
```bash
# Run all working tests
python -m pytest tests/unit/infrastructure/test_fallback_manager_enhanced.py tests/unit/domain/ tests/unit/presentation/ -v
```

### 2. Continuous Integration

#### CI Pipeline Commands
```bash
# Full test suite with coverage
python -m pytest tests/ --cov=src/llm_judge --cov-report=xml --cov-report=html -v

# Critical path tests only
python -m pytest tests/unit/infrastructure/test_fallback_manager_enhanced.py tests/integration/test_llm_judge_integration.py -v

# Performance regression tests
python -m pytest tests/integration/test_error_scenarios_stress.py::TestPerformanceBenchmarks -v
```

### 3. Release Validation

#### Complete Test Suite
```bash
# All tests with detailed reporting
python -m pytest tests/ -v --tb=long --durations=10

# Generate comprehensive reports
python -m pytest tests/ --html=reports/test_report.html --self-contained-html
```

## Environment Configuration

### 1. Test Environment Variables

#### Basic Configuration
```bash
# Set test environment
export ENVIRONMENT=test
export LOG_LEVEL=DEBUG

# Disable real API calls (force mocking)
export FORCE_MOCK_MODE=true

# Test-specific timeouts
export REQUEST_TIMEOUT=5
export MAX_RETRIES=2
```

#### Provider-Specific (for Integration Tests)
```bash
# Optional: Real API testing (use with caution)
export OPENAI_API_KEY=test-key-openai
export ANTHROPIC_API_KEY=test-key-anthropic
export AWS_ACCESS_KEY_ID=test-key-aws
export AWS_SECRET_ACCESS_KEY=test-secret-aws

# Bedrock-specific
export AWS_REGION=us-east-1
export BEDROCK_MODEL=amazon.nova-pro-v1:0
```

### 2. Test Configuration Files

#### pytest.ini Configuration
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
    -ra
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests
    stress: marks tests as stress tests
asyncio_mode = auto
```

#### conftest.py (Global Test Configuration)
```python
# tests/conftest.py
import pytest
import asyncio
import os
from unittest.mock import patch

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
def mock_environment():
    """Auto-mock environment for all tests."""
    with patch.dict(os.environ, {
        'ENVIRONMENT': 'test',
        'LOG_LEVEL': 'DEBUG',
        'FORCE_MOCK_MODE': 'true'
    }):
        yield
```

## Troubleshooting Guide

### 1. Common Issues and Solutions

#### Issue: ImportError for boto3/botocore
```bash
# Error
ImportError: No module named 'boto3'

# Solution 1: Install missing dependencies
pip install boto3 botocore

# Solution 2: Use mock mode
export FORCE_MOCK_MODE=true
python -m pytest tests/unit/infrastructure/test_bedrock_client_comprehensive.py -v
```

#### Issue: AsyncIO Event Loop Errors
```bash
# Error
RuntimeError: There is no current event loop in thread

# Solution: Use proper async fixture
# Ensure conftest.py has event_loop fixture
python -m pytest tests/ -v --asyncio-mode=auto
```

#### Issue: Mock Configuration Errors
```bash
# Error
AttributeError: Mock object has no attribute 'expected_method'

# Solution: Check mock setup in test fixtures
# Add debug prints to verify mock configuration
python -m pytest tests/unit/infrastructure/test_bedrock_client_comprehensive.py::TestBedrockClientInitialization::test_client_initialization_success -v -s
```

#### Issue: Test Timeout
```bash
# Error
FAILED tests/... - asyncio.TimeoutError

# Solution: Increase timeout or check for blocking code
python -m pytest tests/ --timeout=30 -v
```

### 2. Mock Debugging

#### Debug Mock Configuration
```python
# Add to test for debugging
def test_with_debug(mock_client):
    print(f"Mock client: {mock_client}")
    print(f"Mock methods: {dir(mock_client)}")
    print(f"Mock calls: {mock_client.method_calls}")
    
    # Your test code here
    
    print(f"Final mock calls: {mock_client.method_calls}")
```

#### Verify Mock Behavior
```bash
# Run single test with output
python -m pytest tests/unit/infrastructure/test_bedrock_client_comprehensive.py::TestBedrockClientInitialization::test_client_initialization_success -v -s --capture=no
```

### 3. Performance Debugging

#### Identify Slow Tests
```bash
# Show slowest tests
python -m pytest tests/ --durations=0

# Profile specific test
python -m pytest tests/integration/test_error_scenarios_stress.py::test_high_concurrency_evaluations -v --durations=10
```

#### Memory Usage Monitoring
```bash
# Install memory profiler
pip install memory-profiler pytest-monitor

# Run with memory monitoring
python -m pytest tests/ --monitor-memory -v
```

## Test Data Management

### 1. Test Data Files

#### Sample Data Structure
```
tests/
├── data/
│   ├── sample_prompts.json
│   ├── sample_responses.json
│   ├── evaluation_examples.json
│   └── error_scenarios.json
└── fixtures/
    ├── mock_responses/
    │   ├── bedrock_nova_responses.json
    │   ├── bedrock_anthropic_responses.json
    │   └── fallback_responses.json
    └── configurations/
        ├── test_configs.json
        └── mock_configs.json
```

#### Loading Test Data
```python
import json
import os

def load_test_data(filename):
    """Load test data from JSON file."""
    data_path = os.path.join(os.path.dirname(__file__), 'data', filename)
    with open(data_path, 'r') as f:
        return json.load(f)

# Usage in tests
@pytest.fixture
def sample_evaluations():
    return load_test_data('evaluation_examples.json')
```

### 2. Dynamic Test Data Generation

#### Generate Test Cases
```python
import pytest
from itertools import product

# Generate test parameter combinations
@pytest.mark.parametrize("provider,model,criteria", [
    ("anthropic", "claude-sonnet-4", "accuracy"),
    ("openai", "gpt-4", "clarity"), 
    ("bedrock", "amazon.nova-pro-v1:0", "completeness")
])
def test_evaluation_combinations(provider, model, criteria):
    """Test all provider/model/criteria combinations."""
    # Test implementation
    pass
```

## Reporting and Metrics

### 1. Test Reports

#### HTML Report Generation
```bash
# Generate detailed HTML report
python -m pytest tests/ --html=reports/test_report.html --self-contained-html

# Generate with coverage
python -m pytest tests/ --cov=src/llm_judge --cov-report=html:reports/coverage_html --html=reports/test_report.html
```

#### JUnit XML for CI/CD
```bash
# Generate JUnit XML for CI systems
python -m pytest tests/ --junitxml=reports/junit.xml
```

#### Coverage Reports
```bash
# Generate coverage report
python -m pytest tests/ --cov=src/llm_judge --cov-report=xml:reports/coverage.xml --cov-report=term-missing
```

### 2. Metrics Collection

#### Test Execution Metrics
```bash
# Collect timing and performance data
python -m pytest tests/ --benchmark-json=reports/benchmark.json

# Monitor memory usage
python -m pytest tests/ --monitor-memory --monitor-json=reports/memory.json
```

#### Custom Metrics
```python
# Example: Custom performance tracking
import time
import json

class TestMetrics:
    def __init__(self):
        self.metrics = {}
    
    def record_test_time(self, test_name, duration):
        self.metrics[test_name] = {
            'duration': duration,
            'timestamp': time.time()
        }
    
    def save_metrics(self, filename='test_metrics.json'):
        with open(filename, 'w') as f:
            json.dump(self.metrics, f, indent=2)

# Usage in conftest.py
@pytest.fixture(scope="session")
def test_metrics():
    return TestMetrics()
```

## Continuous Integration Integration

### 1. GitHub Actions Configuration

#### Basic Workflow
```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, '3.10', '3.11']
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v3
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements-test.txt
    
    - name: Run working tests
      run: |
        python -m pytest tests/unit/infrastructure/test_fallback_manager_enhanced.py -v
    
    - name: Run integration tests
      run: |
        python -m pytest tests/integration/ -v --tb=short
      continue-on-error: true
    
    - name: Generate coverage report
      run: |
        python -m pytest tests/ --cov=src/llm_judge --cov-report=xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
```

### 2. Local CI Simulation

#### Pre-Commit Hooks
```bash
# Install pre-commit
pip install pre-commit

# Setup hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

#### Local CI Script
```bash
#!/bin/bash
# scripts/run_ci_tests.sh

echo "Running local CI simulation..."

# Set test environment
export ENVIRONMENT=test
export FORCE_MOCK_MODE=true

# Run tests in CI order
echo "1. Running unit tests..."
python -m pytest tests/unit/ -v --tb=short

echo "2. Running integration tests..."
python -m pytest tests/integration/ -v --tb=short

echo "3. Generating coverage report..."
python -m pytest tests/ --cov=src/llm_judge --cov-report=term-missing

echo "4. Running performance tests..."
python -m pytest tests/integration/test_error_scenarios_stress.py::TestPerformanceBenchmarks -v

echo "CI simulation complete!"
```

## Best Practices

### 1. Test Development

#### Writing Effective Tests
```python
# Good test structure
def test_specific_behavior_with_clear_expectation():
    """Test that specific behavior produces expected result."""
    # Arrange
    setup = create_test_setup()
    expected_result = define_expected_outcome()
    
    # Act
    result = perform_operation(setup)
    
    # Assert
    assert result == expected_result
    assert_side_effects_correct()

# Bad: Vague test name and expectations
def test_something():
    result = do_stuff()
    assert result  # What should result be?
```

#### Mock Best Practices
```python
# Good: Specific, focused mocks
@patch('src.module.specific_dependency')
def test_with_focused_mock(mock_dependency):
    mock_dependency.return_value = expected_value
    # Test code
    mock_dependency.assert_called_once_with(expected_args)

# Bad: Over-mocking
@patch('src.module.everything')
def test_with_overmocking(mock_everything):
    # Hard to understand what's being tested
    pass
```

### 2. Test Maintenance

#### Regular Maintenance Tasks
```bash
# Weekly: Check for flaky tests
python -m pytest tests/ --count=5  # Run multiple times

# Monthly: Update test dependencies  
pip-compile requirements-test.in
pip install -r requirements-test.txt

# Per release: Full validation
python -m pytest tests/ --cov=src/llm_judge --cov-fail-under=80
```

#### Test Cleanup
```python
# Always clean up resources
@pytest.fixture
def test_resource():
    resource = create_expensive_resource()
    yield resource
    cleanup_resource(resource)

# Use context managers where possible
async def test_with_cleanup():
    async with managed_resource() as resource:
        # Test code
        pass
    # Automatic cleanup
```

## Conclusion

This test execution guide provides:

- **Clear Execution Strategies**: From quick validation to full CI/CD integration
- **Comprehensive Troubleshooting**: Solutions for common issues and debugging techniques
- **Performance Optimization**: Strategies for efficient test execution
- **Best Practices**: Guidelines for maintainable, reliable tests
- **CI/CD Integration**: Ready-to-use configurations for automated testing

Following this guide ensures consistent, reliable test execution across all environments and development workflows.