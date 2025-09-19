# Structured Output Implementation

This document describes the structured output capabilities implemented across all LLM providers in the llm-as-a-judge system.

## Overview

Structured output ensures that LLM responses conform to a predefined JSON schema, providing reliable and consistent data formats for evaluation and comparison tasks. This implementation leverages each provider's native structured output capabilities where available.

## Supported Providers

### OpenAI

- **Method**: JSON Schema with `response_format` parameter
- **Models**: GPT-4, GPT-4o, GPT-5, and other compatible models
- **Schema Type**: `json_schema` with strict validation

### Anthropic

- **Method**: JSON Schema with `response_format` parameter
- **Models**: Claude-3 Sonnet, Claude-3 Haiku, Claude-3 Opus, and other compatible models
- **Schema Type**: `json_schema` with strict validation

### AWS Bedrock

- **Method**: JSON Schema with `response_format` parameter
- **Models**: Anthropic models on Bedrock, Amazon Nova models
- **Schema Type**: `json_schema` with strict validation

## Implementation Details

### Evaluation Schema

All providers use the same JSON schema for evaluation responses:

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "evaluation_response",
    "strict": true,
    "schema": {
      "type": "object",
      "properties": {
        "score": {
          "type": "integer",
          "minimum": 1,
          "maximum": 5,
          "description": "Evaluation score from 1-5"
        },
        "reasoning": {
          "type": "string",
          "description": "Detailed explanation of the evaluation"
        },
        "confidence": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "Confidence level in the evaluation"
        }
      },
      "required": ["score", "reasoning", "confidence"],
      "additionalProperties": false
    }
  }
}
```

### Comparison Schema

All providers use the same JSON schema for comparison responses:

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "comparison_response",
    "strict": true,
    "schema": {
      "type": "object",
      "properties": {
        "winner": {
          "type": "string",
          "enum": ["A", "B", "tie"],
          "description": "Which response is better: A, B, or tie"
        },
        "reasoning": {
          "type": "string",
          "description": "Detailed explanation of the comparison"
        },
        "confidence": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "Confidence level in the comparison"
        }
      },
      "required": ["winner", "reasoning", "confidence"],
      "additionalProperties": false
    }
  }
}
```

## Usage Examples

### OpenAI Structured Output

```python
from llm_judge.infrastructure.clients.openai_client import OpenAIClient
from llm_judge.infrastructure.config.config import LLMConfig

config = LLMConfig(openai_api_key="your-key")
client = OpenAIClient(config)

# Evaluation with structured output
result = await client.evaluate_with_openai(
    prompt="What is the capital of France?",
    response_text="Paris is the capital of France.",
    criteria="accuracy"
)

# Result will be guaranteed to have the correct structure:
# {
#   "score": 5,  # Integer between 1-5
#   "reasoning": "The response is completely accurate...",
#   "confidence": 0.95
# }
```

### Anthropic Structured Output

```python
from llm_judge.infrastructure.clients.anthropic_client import AnthropicClient

client = AnthropicClient(config)

# Comparison with structured output
result = await client.compare_with_anthropic(
    prompt="Explain photosynthesis",
    response_a="Photosynthesis is the process...",
    response_b="Plants use sunlight to make food..."
)

# Result will be guaranteed to have the correct structure:
# {
#   "winner": "A",
#   "reasoning": "Response A provides more detailed explanation...",
#   "confidence": 0.85
# }
```

### Bedrock Structured Output

```python
from llm_judge.infrastructure.clients.bedrock_client import BedrockClient

client = BedrockClient(config)

# Evaluation with structured output
result = await client.evaluate_with_bedrock(
    prompt="Solve this math problem: 2 + 2",
    response_text="2 + 2 = 4",
    criteria="correctness"
)
```

## Fallback Handling

When structured output fails or returns invalid JSON, the system implements intelligent fallback parsing:

1. **JSON Parsing Error**: Attempts to extract JSON from code blocks (`json ... `)
2. **Validation Error**: Falls back to sentiment analysis of the response text
3. **Default Values**: Provides reasonable defaults with low confidence scores

### Fallback Scoring Logic

The system uses keyword-based sentiment analysis as a fallback:

- **Score 5**: "excellent", "outstanding" (integer)
- **Score 4**: "good", "well" (integer)
- **Score 3**: Default/neutral (integer)
- **Score 2**: "poor", "bad" (integer)
- **Score 1**: "terrible", "awful" (integer)

## Benefits

### Reliability

- **Guaranteed Structure**: Responses always conform to expected schema
- **Type Safety**: Proper data types and value ranges enforced
- **Validation**: Required fields and constraints validated

### Consistency

- **Unified Interface**: Same schema across all providers
- **Predictable Output**: Consistent field names and types
- **Error Handling**: Standardized fallback mechanisms

### Performance

- **Reduced Parsing**: No need for complex text parsing
- **Faster Processing**: Direct JSON deserialization
- **Lower Error Rates**: Fewer parsing failures

## Configuration

Structured output is enabled by default for all evaluation and comparison methods. No additional configuration is required.

### Provider-Specific Notes

#### OpenAI

- Uses `response_format` parameter in chat completions
- Compatible with GPT-4, GPT-4o, and GPT-5 models
- Supports both temperature and reasoning_effort parameters

#### Anthropic

- Uses `response_format` parameter in message creation
- Compatible with Claude-3 family models
- Supports both temperature and top_p parameters

#### Bedrock

- Uses `response_format` in request body
- Compatible with Anthropic models on Bedrock
- Supports Amazon Nova models with `responseFormat` field

## Testing

Comprehensive tests are available in:

- `tests/unit/infrastructure/test_structured_output_simple.py` - Schema validation and fallback logic
- `tests/unit/infrastructure/test_structured_output.py` - Full integration tests (requires API keys)

Run tests with:

```bash
pytest tests/unit/infrastructure/test_structured_output_simple.py -v
```

## Error Handling

The system handles various error scenarios:

1. **Invalid JSON**: Falls back to sentiment analysis
2. **Missing Fields**: Provides default values with low confidence
3. **Type Mismatches**: Validates and corrects data types
4. **Out-of-Range Values**: Clamps values to valid ranges

## Future Enhancements

Potential improvements for structured output:

1. **Custom Schemas**: Allow user-defined schemas for specific use cases
2. **Multi-Criteria Evaluation**: Support for multiple evaluation dimensions
3. **Nested Structures**: Support for complex nested JSON schemas
4. **Schema Validation**: Runtime validation of custom schemas
5. **Performance Metrics**: Track structured output success rates

## Troubleshooting

### Common Issues

1. **Schema Validation Errors**: Ensure all required fields are present
2. **Type Mismatches**: Check that numeric values are within valid ranges
3. **Provider Compatibility**: Verify that the model supports structured output

### Debug Mode

Enable debug logging to see structured output details:

```python
import logging
logging.getLogger('llm_judge.infrastructure.clients').setLevel(logging.DEBUG)
```

This will log the response format being sent and the parsed results.
