# Test Fixtures

This directory contains test fixtures and sample data used by the test suite.

## Directory Structure

```
fixtures/
├── README.md              # This file
└── sample_data/           # Sample data for testing
    ├── minimal_batch.jsonl         # Minimal batch test data (3 entries)
    ├── test_batch.jsonl            # Standard test batch data  
    └── sample_batch_results.json   # Sample batch evaluation results
```

## Sample Data Files

### Input Files (.jsonl)

#### `minimal_batch.jsonl`
- **Purpose**: Minimal test data for basic functionality testing
- **Entries**: 3 simple evaluation cases
- **Usage**: Quick integration tests, basic functionality validation
- **Format**: JSONL with `prompt`, `response`, `model`, `criteria` fields

#### `test_batch.jsonl`
- **Purpose**: Standard test scenarios for comprehensive testing
- **Entries**: Multiple diverse evaluation scenarios
- **Usage**: Integration tests, batch processing validation
- **Format**: JSONL with various criteria and complexity levels

### Output Files (.json)

#### `sample_batch_results.json`
- **Purpose**: Example of expected batch evaluation output format
- **Usage**: Output format validation, result parsing tests
- **Format**: JSON with results array and summary statistics

## Usage in Tests

### Loading Test Data

```python
import json
import os
from pathlib import Path

def load_test_batch(filename):
    """Load test batch data from fixtures."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "sample_data"
    file_path = fixtures_dir / filename
    
    with open(file_path, 'r') as f:
        return [json.loads(line) for line in f if line.strip()]

# Usage in tests
@pytest.fixture
def minimal_test_data():
    return load_test_batch("minimal_batch.jsonl")

@pytest.fixture 
def standard_test_data():
    return load_test_batch("test_batch.jsonl")
```

### Sample Test Pattern

```python
import pytest
from tests.fixtures.sample_data import load_test_batch

class TestBatchProcessing:
    @pytest.fixture
    def test_data(self):
        return load_test_batch("minimal_batch.jsonl")
    
    def test_batch_evaluation(self, test_data):
        """Test batch evaluation with sample data."""
        # Test implementation using sample data
        assert len(test_data) == 3
        assert all('prompt' in item for item in test_data)
```

## File Formats

### Input JSONL Format
```json
{"prompt": "What is AI?", "response": "AI is artificial intelligence", "model": "test-model", "criteria": "accuracy"}
{"prompt": "Explain ML", "response": "Machine learning is...", "model": "test-model", "criteria": "clarity"}
```

### Output JSON Format
```json
{
  "results": [
    {
      "prompt": "What is AI?",
      "response": "AI is artificial intelligence", 
      "evaluation": {
        "score": 4.2,
        "reasoning": "Clear but basic definition",
        "confidence": 0.85
      },
      "metadata": {
        "judge_model": "test-model",
        "evaluation_time": "2025-09-06T08:00:00Z"
      }
    }
  ],
  "summary": {
    "total_evaluated": 1,
    "average_score": 4.2
  }
}
```

## Creating New Test Data

### Guidelines

1. **Small Size**: Keep test data minimal for fast execution
2. **Representative**: Cover typical use cases and edge cases
3. **Clear Purpose**: Each file should have a specific testing purpose
4. **Valid Format**: Ensure proper JSON/JSONL formatting
5. **Version Control**: Track changes to test data

### Adding New Fixtures

1. Create the fixture file in `sample_data/`
2. Add description to this README
3. Create helper functions for loading the data
4. Update relevant tests to use the new fixture
5. Document the expected usage and format

## Data Maintenance

### Regular Tasks

- **Validation**: Ensure all fixture files have valid format
- **Cleanup**: Remove unused or outdated fixtures  
- **Updates**: Keep fixtures aligned with current system capabilities
- **Documentation**: Update this README when adding new fixtures

### Quality Checks

```bash
# Validate JSONL files
python -c "
import json
with open('tests/fixtures/sample_data/minimal_batch.jsonl') as f:
    for i, line in enumerate(f, 1):
        try:
            json.loads(line)
        except json.JSONDecodeError as e:
            print(f'Line {i}: {e}')
"

# Validate JSON files  
python -c "
import json
with open('tests/fixtures/sample_data/sample_batch_results.json') as f:
    json.load(f)
print('Valid JSON')
"
```

## Integration with Test Suite

These fixtures are used by:

- **Unit Tests**: For consistent input data
- **Integration Tests**: For end-to-end workflow validation  
- **Performance Tests**: For load testing scenarios
- **Regression Tests**: For ensuring consistent behavior
- **Mock Data**: For external API simulation

The fixtures provide standardized, version-controlled test data that ensures consistent and reliable test execution across all test categories.