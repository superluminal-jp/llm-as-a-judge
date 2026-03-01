# LLM-as-a-Judge

[![Tests](https://img.shields.io/badge/tests-58%20passing-brightgreen)](#testing)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://python.org)
[![AWS Lambda](https://img.shields.io/badge/runtime-AWS%20Lambda-orange)](https://aws.amazon.com/lambda/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Synchronous AWS Lambda function that evaluates LLM-generated responses against a multi-criteria rubric using Anthropic, OpenAI, or Amazon Bedrock as the judge model.

## Architecture

```
Lambda Event (prompt, response, [provider], [criteria_file])
    └─→ handler.lambda_handler
        ├─→ criteria.load_from_s3()   or   DefaultCriteria.balanced()
        ├─→ providers.get_provider()  → AnthropicProvider / OpenAIProvider / BedrockProvider
        └─→ evaluator.evaluate()
              ├─→ build_evaluation_prompt()
              ├─→ provider.complete()
              └─→ parse_evaluation_response()
                  └─→ { overall_score, criterion_scores, reasoning, judge_model, provider }
```

### Project Structure

```
src/
├── __init__.py
├── handler.py          # Lambda entry point, exception hierarchy
├── evaluator.py        # Prompt construction, LLM call, JSON parsing, scoring
├── criteria.py         # EvaluationCriteria dataclass, S3 loader, defaults
├── config.py           # Env-var Config dataclass with cold-start caching
└── providers/
    ├── __init__.py     # BaseProvider protocol + get_provider() factory
    ├── anthropic.py    # Synchronous Anthropic client
    ├── openai.py       # Synchronous OpenAI client
    └── bedrock.py      # Bedrock converse API (IAM auth)

tests/
├── conftest.py         # Shared fixtures (mock LLM responses, events, context)
├── test_handler.py     # lambda_handler() tests
├── test_evaluator.py   # Prompt building and response parsing tests
├── test_criteria.py    # EvaluationCriteria and S3 loader tests
└── test_providers.py   # Provider client tests

cdk/
├── app.py              # CDK App entry point
├── stack.py            # LlmJudgeStack (Lambda + IAM + env vars)
└── requirements.txt    # CDK dependencies

scripts/
└── deploy.sh           # Bootstrap + cdk deploy wrapper
```

## Lambda Event

```json
{
  "prompt": "What is machine learning?",
  "response": "Machine learning is a subset of AI...",
  "provider": "bedrock",
  "judge_model": "amazon.nova-lite-v1:0",
  "criteria_file": "s3://my-bucket/criteria/custom.json"
}
```

| Field | Required | Default |
|-------|----------|---------|
| `prompt` | ✅ | — |
| `response` | ✅ | — |
| `provider` | ✗ | `DEFAULT_PROVIDER` env var |
| `judge_model` | ✗ | Provider-specific env var |
| `criteria_file` | ✗ | Default balanced criteria |

## Lambda Response

```json
{
  "overall_score": 4.75,
  "criterion_scores": {
    "accuracy": 5.0,
    "clarity": 5.0,
    "helpfulness": 5.0,
    "completeness": 4.0
  },
  "reasoning": "The response is factually correct and clearly explains...",
  "judge_model": "amazon.nova-lite-v1:0",
  "provider": "bedrock"
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_PROVIDER` | `anthropic` | LLM provider when event omits `provider` |
| `ANTHROPIC_API_KEY` | — | Required for Anthropic provider |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Default Anthropic judge model |
| `OPENAI_API_KEY` | — | Required for OpenAI provider |
| `OPENAI_MODEL` | `gpt-4o` | Default OpenAI judge model |
| `BEDROCK_MODEL` | `amazon.nova-lite-v1:0` | Default Bedrock judge model |
| `REQUEST_TIMEOUT` | `30` | HTTP timeout in seconds |
| `LOG_LEVEL` | `INFO` | Powertools log level |
| `POWERTOOLS_SERVICE_NAME` | `llm-judge` | Lambda Powertools service tag |

> Bedrock uses IAM authentication via the Lambda execution role — no API key required.

## Criteria File (S3)

Custom evaluation criteria can be loaded from an S3 JSON file:

```json
{
  "name": "Technical Evaluation",
  "criteria": [
    {
      "name": "accuracy",
      "description": "Factual correctness of the response",
      "weight": 0.5,
      "evaluation_prompt": "Check whether all technical claims are correct"
    },
    {
      "name": "clarity",
      "description": "Clarity and readability",
      "weight": 0.5
    }
  ]
}
```

Pass the S3 URI in the event: `"criteria_file": "s3://my-bucket/criteria.json"`

Lambda execution role must have `s3:GetObject` on the bucket (configured via `criteria_bucket_arn` CDK context).

## Error Handling

All errors propagate via exceptions (never `return {"error": ...}`):

| Exception | Cause |
|-----------|-------|
| `ValidationError` | Missing/invalid event fields |
| `ConfigurationError` | Missing API key or unknown provider |
| `ProviderError` | LLM API failure (auth, rate limit, parse error) |
| `CriteriaLoadError` | S3 object not found or invalid JSON |

## Local Development

```bash
# Install runtime and dev dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Run all tests
pytest

# Run tests with coverage report
pytest --cov=src --cov-report=term-missing

# Run a specific test file
pytest tests/test_evaluator.py -v
```

## Deployment

### Prerequisites

- AWS CLI configured with appropriate credentials
- CDK CLI: `npm install -g aws-cdk`
- Docker running (for CDK asset bundling)

### Quick deploy

```bash
# Set required environment variables
export ANTHROPIC_API_KEY=sk-ant-...   # if using Anthropic

# Deploy (bootstraps CDK on first run)
./scripts/deploy.sh

# Deploy to a specific region
./scripts/deploy.sh --region us-east-1

# Deploy with S3 criteria bucket access
CRITERIA_BUCKET_ARN=arn:aws:s3:::my-bucket ./scripts/deploy.sh
```

### Manual CDK deploy

```bash
pip install -r cdk/requirements.txt
cdk bootstrap
cdk deploy LlmJudgeStack \
  --app "python3 cdk/app.py" \
  --require-approval never \
  --context criteria_bucket_arn=arn:aws:s3:::my-bucket
```

### Lambda configuration (post-deploy)

Set API keys via the Lambda console or AWS CLI:

```bash
aws lambda update-function-configuration \
  --function-name <function-name> \
  --environment "Variables={ANTHROPIC_API_KEY=sk-ant-...,DEFAULT_PROVIDER=anthropic}"
```

### Invoke

```bash
aws lambda invoke \
  --function-name <function-name> \
  --payload '{"prompt":"What is ML?","response":"ML is...","provider":"bedrock"}' \
  --cli-binary-format raw-in-base64-out \
  result.json && cat result.json
```

## Testing

58 tests, no real API calls (all mocked with `unittest.mock` + `moto[s3]`):

```bash
pytest                                          # all tests
pytest tests/test_handler.py -v                 # handler tests
pytest tests/test_evaluator.py -v               # evaluator tests
pytest tests/test_criteria.py -v                # criteria + S3 tests
pytest tests/test_providers.py -v               # provider client tests
pytest --cov=src --cov-report=term-missing      # with coverage (92%)
```

## CDK Stack Resources

- **Lambda function**: Python 3.12, 512 MB, 60-second timeout
- **IAM policy**: `bedrock:InvokeModel` + `bedrock:Converse` on all foundation models
- **IAM policy** (optional): `s3:GetObject` on the criteria bucket
- **CloudWatch Logs**: Auto-created by Lambda runtime
- **Outputs**: `LambdaFunctionArn`, `LambdaFunctionName`

## License

MIT
