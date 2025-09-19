# AWS Bedrock Integration

This document describes the AWS Bedrock integration that has been added to the LLM-as-a-Judge system.

## Overview

AWS Bedrock support has been fully integrated into the LLM-as-a-Judge system, allowing you to use Amazon's foundation models (like Nova and Anthropic models on Bedrock) as judges for evaluation and comparison tasks.

## Features Implemented

### 1. **Bedrock Client** (`src/llm_judge/infrastructure/clients/bedrock_client.py`)
- Full AWS Bedrock API integration
- Support for both Amazon Nova and Anthropic models on Bedrock
- Automatic request/response format conversion
- Comprehensive error handling with AWS-specific error classification
- Retry logic and timeout management
- Structured evaluation and comparison methods

### 2. **Configuration Support** 
- Added AWS credentials configuration (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN)
- AWS region configuration (AWS_REGION)
- Bedrock model selection (BEDROCK_MODEL)
- Provider selection (DEFAULT_PROVIDER=bedrock)
- Temperature control for Bedrock models

### 3. **Error Classification**
- AWS-specific error patterns (ThrottlingException, AccessDeniedException, etc.)
- Proper error categorization for Bedrock API responses
- User-friendly error messages with AWS context
- Retry strategies tailored for AWS service patterns

### 4. **CLI Integration**
- Added 'bedrock' as a valid provider option in CLI commands
- Full CLI support for all Bedrock functionality
- Consistent interface with existing OpenAI/Anthropic providers

### 5. **Service Integration**
- Full integration with LLMJudge service
- Fallback mechanisms when Bedrock is unavailable
- Multi-criteria evaluation support (ready for extension)

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# AWS Bedrock Configuration
DEFAULT_PROVIDER=bedrock
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_REGION=us-east-1

# Model Configuration  
BEDROCK_MODEL=amazon.nova-premier-v1:0
# Alternative models:
# BEDROCK_MODEL=anthropic.claude-opus-4-1-20250805-v1:0

# Optional: Temperature control
BEDROCK_TEMPERATURE=0.1

# Optional: Timeout settings
BEDROCK_REQUEST_TIMEOUT=30
BEDROCK_CONNECT_TIMEOUT=10
```

## Supported Models

### Amazon Nova Models
- `amazon.nova-premier-v1:0` (recommended)
- Other Nova variants as they become available

### Anthropic Models on Bedrock
- `anthropic.claude-opus-4-1-20250805-v1:0`
- `anthropic.claude-3-sonnet-20240229-v1:0`
- Other Anthropic models available on Bedrock

## Usage Examples

### CLI Usage

```bash
# Evaluate with Bedrock
llm-judge evaluate "What is AI?" "AI is artificial intelligence" --provider bedrock

# Compare responses
llm-judge compare "Explain ML" "Response A" "Response B" --provider bedrock

# Use specific Bedrock model
llm-judge evaluate "Question" "Answer" --provider bedrock --judge-model amazon.nova-premier-v1:0
```

### Python API Usage

```python
import asyncio
from llm_judge.application.services.llm_judge_service import LLMJudge, CandidateResponse
from llm_judge.infrastructure.config.config import LLMConfig

# Configure for Bedrock
config = LLMConfig(
    aws_access_key_id="your-access-key",
    aws_secret_access_key="your-secret-key", 
    aws_region="us-east-1",
    default_provider="bedrock",
    bedrock_model="amazon.nova-premier-v1:0"
)

async def evaluate_with_bedrock():
    judge = LLMJudge(config=config)
    
    candidate = CandidateResponse(
        prompt="What is artificial intelligence?",
        response="AI is the simulation of human intelligence in machines.",
        model="test-model"
    )
    
    result = await judge.evaluate_response(candidate, criteria="accuracy and clarity")
    print(f"Score: {result.score}/5")
    print(f"Reasoning: {result.reasoning}")
    
    await judge.close()

# Run evaluation
asyncio.run(evaluate_with_bedrock())
```

## Requirements

### Required Dependencies
- `boto3` - AWS SDK for Python
- `botocore` - Low-level AWS service client

Install with:
```bash
pip install boto3
```

### AWS Permissions

Your AWS credentials need access to:
- `bedrock:InvokeModel` - To call foundation models
- `bedrock:ListFoundationModels` - To list available models (optional)

Example IAM policy:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:ListFoundationModels"
            ],
            "Resource": "*"
        }
    ]
}
```

## Error Handling

The system includes comprehensive error handling for AWS Bedrock:

- **Authentication Errors**: Invalid credentials, expired tokens
- **Rate Limiting**: Throttling exceptions, quota exceeded
- **Validation Errors**: Invalid model IDs, malformed requests
- **Service Errors**: Temporary unavailability, internal server errors
- **Network Errors**: Connection issues, timeouts

Each error type has appropriate retry strategies and user-friendly messages.

## Testing

The integration has been tested with:
- Configuration validation
- Client initialization (mocked)
- Service integration
- Error classification
- CLI integration

To test without actual AWS credentials:
```bash
PYTHONPATH=src python -c "
from llm_judge.infrastructure.config.config import LLMConfig
config = LLMConfig(
    aws_access_key_id='test',
    aws_secret_access_key='test',
    default_provider='bedrock'
)
print(f'Provider: {config.default_provider}')
print(f'Model: {config.bedrock_model}')
"
```

## Architecture

The Bedrock integration follows the same architectural patterns as existing providers:

```
Application Layer (LLMJudge)
    ↓
Infrastructure Layer (BedrockClient)
    ↓
AWS Bedrock API (via boto3)
```

Key components:
- **BedrockClient**: Handles AWS API communication
- **Error Classification**: AWS-specific error handling
- **Configuration**: AWS credentials and settings
- **Retry Logic**: AWS service-aware retry strategies

## Future Enhancements

Potential areas for future improvement:
- Multi-criteria client for Bedrock (similar to OpenAI/Anthropic)
- Support for streaming responses
- Model-specific parameter optimization
- Cost tracking and optimization
- Integration with AWS CloudWatch for monitoring

## Support

For issues related to Bedrock integration:
1. Verify AWS credentials and permissions
2. Check network connectivity to AWS services
3. Ensure boto3 is properly installed
4. Review error logs for specific AWS error codes

For general LLM-as-a-Judge support, see the main README.md.