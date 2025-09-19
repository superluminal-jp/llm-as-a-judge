# Configuration Guide

## Overview

This guide covers all configuration options for the LLM-as-a-Judge system, including multi-criteria evaluation settings, LLM provider configuration, and performance tuning options.

## Configuration Methods

### 1. Environment Variables (.env file)

Create a `.env` file in the project root:

```bash
# LLM Provider API Keys
OPENAI_API_KEY=sk-your-openai-api-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# Default Provider (openai or anthropic)
DEFAULT_PROVIDER=anthropic

# Model Configuration
OPENAI_MODEL=gpt-4
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# Timeout Configuration (seconds)
REQUEST_TIMEOUT=30
CONNECT_TIMEOUT=10

# Retry Configuration
MAX_RETRIES=3
RETRY_BACKOFF_FACTOR=2.0

# Logging Configuration
LOG_LEVEL=INFO
ENABLE_AUDIT_LOGGING=true

# Multi-Criteria Configuration
DEFAULT_CRITERIA_TYPE=comprehensive
MULTI_CRITERIA_TIMEOUT=60
```

### Criteria Type Options

The `DEFAULT_CRITERIA_TYPE` environment variable controls which default evaluation criteria set to use:

- **`comprehensive`** (default): 7-criteria evaluation covering accuracy, completeness, clarity, relevance, helpfulness, coherence, and appropriateness
- **`basic`**: 3-criteria evaluation focusing on accuracy, clarity, and helpfulness
- **`technical`**: 5-criteria evaluation optimized for technical content (technical accuracy, implementation feasibility, best practices, completeness, clarity)
- **`creative`**: 5-criteria evaluation for creative content (creativity, engagement, coherence, relevance, style)

### 2. Configuration File (JSON/YAML)

Create `config.json`:

```json
{
  "llm_providers": {
    "openai": {
      "api_key": "sk-your-openai-key",
      "model": "gpt-4",
      "max_tokens": 4000,
      "temperature": 0.1
    },
    "anthropic": {
      "api_key": "sk-ant-your-anthropic-key",
      "model": "claude-sonnet-4-20250514",
      "max_tokens": 4000,
      "temperature": 0.1
    }
  },
  "default_provider": "anthropic",
  "request_settings": {
    "timeout": 30,
    "connect_timeout": 10,
    "max_retries": 3,
    "backoff_factor": 2.0
  },
  "multi_criteria_settings": {
    "enabled_by_default": true,
    "timeout": 60,
    "fallback_on_error": true,
    "default_criteria_type": "comprehensive"
  },
  "batch_processing": {
    "max_concurrent": 10,
    "retry_failed": true,
    "max_retries_per_item": 3
  },
  "logging": {
    "level": "INFO",
    "enable_audit": true,
    "log_file": "logs/llm_judge.log"
  }
}
```

Use configuration file:

```bash
python -m src.llm_judge --config config.json evaluate "Question" "Answer"
```

### 3. Programmatic Configuration

```python
from src.llm_judge.infrastructure.config.config import LLMConfig
from src.llm_judge import LLMJudge

# Create configuration object
config = LLMConfig(
    # LLM Provider Settings
    openai_api_key="sk-your-openai-key",
    anthropic_api_key="sk-ant-your-anthropic-key",
    default_provider="anthropic",
    openai_model="gpt-4",
    anthropic_model="claude-sonnet-4-20250514",

    # Request Settings
    request_timeout=30,
    connect_timeout=10,
    max_retries=3,

    # Multi-Criteria Settings
    enable_multi_criteria_by_default=True,
    multi_criteria_timeout=60,

    # Logging
    log_level="INFO",
    enable_audit_logging=True
)

judge = LLMJudge(config=config)
```

## Configuration Options Reference

### LLM Provider Configuration

#### OpenAI Settings

| Parameter            | Type  | Default | Description                         |
| -------------------- | ----- | ------- | ----------------------------------- |
| `openai_api_key`     | str   | None    | OpenAI API key                      |
| `openai_model`       | str   | "gpt-4" | OpenAI model to use                 |
| `openai_max_tokens`  | int   | 4000    | Maximum tokens per request          |
| `openai_temperature` | float | 0.1     | Temperature for response generation |
| `openai_base_url`    | str   | None    | Custom OpenAI API base URL          |

#### Anthropic Settings

| Parameter               | Type  | Default                    | Description                         |
| ----------------------- | ----- | -------------------------- | ----------------------------------- |
| `anthropic_api_key`     | str   | None                       | Anthropic API key                   |
| `anthropic_model`       | str   | "claude-sonnet-4-20250514" | Anthropic model to use              |
| `anthropic_max_tokens`  | int   | 4000                       | Maximum tokens per request          |
| `anthropic_temperature` | float | 0.1                        | Temperature for response generation |

#### Provider Selection

| Parameter           | Type | Default     | Description                                    |
| ------------------- | ---- | ----------- | ---------------------------------------------- |
| `default_provider`  | str  | "anthropic" | Primary LLM provider ("openai" or "anthropic") |
| `fallback_provider` | str  | None        | Fallback provider if primary fails             |
| `enable_fallback`   | bool | True        | Enable automatic fallback between providers    |

### Multi-Criteria Evaluation Settings

| Parameter                          | Type | Default         | Description                                                              |
| ---------------------------------- | ---- | --------------- | ------------------------------------------------------------------------ |
| `enable_multi_criteria_by_default` | bool | True            | Use multi-criteria evaluation by default                                 |
| `default_criteria_set`             | str  | "comprehensive" | Default criteria set ("comprehensive", "basic", "technical", "creative") |
| `multi_criteria_timeout`           | int  | 60              | Timeout for multi-criteria evaluation (seconds)                          |
| `fallback_on_parsing_error`        | bool | True            | Fallback to mock evaluation on JSON parsing errors                       |
| `validate_criteria_responses`      | bool | True            | Validate LLM responses against expected criteria                         |
| `criteria_weights_validation`      | bool | False           | Validate that criteria weights sum to 1.0                                |

### Request and Timeout Settings

| Parameter              | Type  | Default | Description                       |
| ---------------------- | ----- | ------- | --------------------------------- |
| `request_timeout`      | int   | 30      | HTTP request timeout (seconds)    |
| `connect_timeout`      | int   | 10      | Connection timeout (seconds)      |
| `read_timeout`         | int   | 30      | Response read timeout (seconds)   |
| `max_retries`          | int   | 3       | Maximum retry attempts            |
| `retry_backoff_factor` | float | 2.0     | Exponential backoff factor        |
| `retry_max_wait`       | float | 60.0    | Maximum wait time between retries |

### Batch Processing Configuration

| Parameter                  | Type | Default | Description                                  |
| -------------------------- | ---- | ------- | -------------------------------------------- |
| `max_concurrent_items`     | int  | 10      | Maximum concurrent evaluations               |
| `batch_timeout`            | int  | 3600    | Overall batch timeout (seconds)              |
| `retry_failed_items`       | bool | True    | Retry failed batch items                     |
| `max_retries_per_item`     | int  | 3       | Maximum retries per batch item               |
| `continue_on_error`        | bool | True    | Continue processing if individual items fail |
| `progress_update_interval` | int  | 5       | Progress update frequency (items)            |

### Logging Configuration

| Parameter              | Type | Default  | Description                                 |
| ---------------------- | ---- | -------- | ------------------------------------------- |
| `log_level`            | str  | "INFO"   | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `enable_audit_logging` | bool | False    | Enable audit logging for evaluations        |
| `log_file`             | str  | None     | Log file path (None for console only)       |
| `log_format`           | str  | Standard | Log message format                          |
| `log_request_details`  | bool | False    | Log detailed request/response information   |

### Performance and Caching

| Parameter                    | Type | Default | Description                      |
| ---------------------------- | ---- | ------- | -------------------------------- |
| `enable_result_caching`      | bool | False   | Cache evaluation results         |
| `cache_ttl`                  | int  | 3600    | Cache time-to-live (seconds)     |
| `max_cache_size`             | int  | 1000    | Maximum number of cached results |
| `enable_request_compression` | bool | True    | Enable HTTP request compression  |
| `connection_pool_size`       | int  | 20      | HTTP connection pool size        |

## Advanced Configuration Scenarios

### High-Volume Processing

For high-volume batch processing:

```json
{
  "default_provider": "openai",
  "request_settings": {
    "timeout": 15,
    "connect_timeout": 5,
    "max_retries": 2
  },
  "batch_processing": {
    "max_concurrent": 20,
    "retry_failed": false,
    "max_retries_per_item": 1
  },
  "multi_criteria_settings": {
    "enabled_by_default": false,
    "default_criteria_set": "basic"
  },
  "performance": {
    "enable_result_caching": true,
    "cache_ttl": 7200,
    "connection_pool_size": 50
  }
}
```

### Research and Analysis

For detailed research evaluations:

```json
{
  "default_provider": "anthropic",
  "multi_criteria_settings": {
    "enabled_by_default": true,
    "timeout": 120,
    "default_criteria_set": "comprehensive",
    "validate_criteria_responses": true
  },
  "request_settings": {
    "timeout": 60,
    "max_retries": 5
  },
  "batch_processing": {
    "max_concurrent": 5,
    "retry_failed": true,
    "max_retries_per_item": 5
  },
  "logging": {
    "level": "DEBUG",
    "enable_audit": true,
    "log_request_details": true
  }
}
```

### Cost-Optimized Setup

For cost-conscious deployments:

```json
{
  "default_provider": "openai",
  "llm_providers": {
    "openai": {
      "model": "gpt-3.5-turbo",
      "max_tokens": 2000,
      "temperature": 0.0
    }
  },
  "multi_criteria_settings": {
    "enabled_by_default": false
  },
  "batch_processing": {
    "max_concurrent": 5
  },
  "performance": {
    "enable_result_caching": true,
    "cache_ttl": 86400
  }
}
```

### Development and Testing

For development environments:

```json
{
  "default_provider": "anthropic",
  "multi_criteria_settings": {
    "enabled_by_default": true,
    "fallback_on_parsing_error": true
  },
  "request_settings": {
    "timeout": 10,
    "max_retries": 1
  },
  "logging": {
    "level": "DEBUG",
    "enable_audit": false
  },
  "development": {
    "enable_mock_fallback": true,
    "mock_delay": 1.0
  }
}
```

## Custom Criteria Configuration

### Defining Custom Criteria Sets

```python
from src.llm_judge.domain.evaluation.criteria import (
    EvaluationCriteria, CriterionDefinition, CriterionType
)

# Define custom criteria for technical documentation
tech_doc_criteria = EvaluationCriteria(
    name="technical_documentation",
    description="Evaluation criteria for technical documentation",
    criteria=[
        CriterionDefinition(
            name="technical_accuracy",
            description="Correctness of technical information",
            criterion_type=CriterionType.FACTUAL,
            weight=0.3,
            scale_min=1,
            scale_max=5,
            examples={
                5: "All technical details are accurate and current",
                3: "Generally accurate with minor technical issues",
                1: "Contains significant technical errors"
            }
        ),
        CriterionDefinition(
            name="clarity_for_target_audience",
            description="Appropriate clarity for intended audience",
            criterion_type=CriterionType.QUALITATIVE,
            weight=0.25,
            examples={
                5: "Perfect clarity for target audience level",
                3: "Mostly clear with some confusing sections",
                1: "Unclear or inappropriate for target audience"
            }
        ),
        CriterionDefinition(
            name="completeness_of_coverage",
            description="Comprehensive coverage of the topic",
            criterion_type=CriterionType.STRUCTURAL,
            weight=0.25
        ),
        CriterionDefinition(
            name="practical_usefulness",
            description="Practical value and actionability",
            criterion_type=CriterionType.CONTEXTUAL,
            weight=0.2
        )
    ],
    validate_weights=True,
    normalize_weights=False
)

# Use custom criteria
result = await judge.evaluate_multi_criteria(candidate, criteria=tech_doc_criteria)
```

### Criteria Configuration File

Save custom criteria in JSON:

```json
{
  "criteria_sets": {
    "technical_documentation": {
      "name": "technical_documentation",
      "description": "Evaluation for technical documentation",
      "criteria": [
        {
          "name": "technical_accuracy",
          "description": "Correctness of technical information",
          "type": "factual",
          "weight": 0.3,
          "scale_min": 1,
          "scale_max": 5,
          "examples": {
            "5": "All technical details are accurate",
            "3": "Generally accurate with minor issues",
            "1": "Contains significant technical errors"
          }
        },
        {
          "name": "clarity_for_audience",
          "description": "Appropriate clarity for intended audience",
          "type": "qualitative",
          "weight": 0.25
        }
      ]
    },
    "code_review": {
      "name": "code_review",
      "description": "Code review evaluation",
      "criteria": [
        {
          "name": "correctness",
          "description": "Code correctness and functionality",
          "type": "factual",
          "weight": 0.4
        },
        {
          "name": "readability",
          "description": "Code readability and style",
          "type": "qualitative",
          "weight": 0.3
        },
        {
          "name": "efficiency",
          "description": "Performance and efficiency",
          "type": "structural",
          "weight": 0.3
        }
      ]
    }
  }
}
```

Load custom criteria:

```python
import json
from src.llm_judge.domain.evaluation.criteria import EvaluationCriteria

# Load criteria from file
with open("custom_criteria.json") as f:
    criteria_config = json.load(f)

# Create criteria from config (implementation would parse the JSON)
tech_criteria = create_criteria_from_config(
    criteria_config["criteria_sets"]["technical_documentation"]
)

result = await judge.evaluate_multi_criteria(candidate, criteria=tech_criteria)
```

## Environment-Specific Configuration

### Production Environment

```bash
# Production .env
OPENAI_API_KEY=sk-prod-key-here
ANTHROPIC_API_KEY=sk-ant-prod-key-here
DEFAULT_PROVIDER=anthropic
LOG_LEVEL=WARNING
ENABLE_AUDIT_LOGGING=true
MAX_CONCURRENT_ITEMS=15
REQUEST_TIMEOUT=45
ENABLE_RESULT_CACHING=true
```

### Staging Environment

```bash
# Staging .env
OPENAI_API_KEY=sk-staging-key-here
ANTHROPIC_API_KEY=sk-ant-staging-key-here
DEFAULT_PROVIDER=anthropic
LOG_LEVEL=INFO
ENABLE_AUDIT_LOGGING=true
MAX_CONCURRENT_ITEMS=8
REQUEST_TIMEOUT=30
ENABLE_RESULT_CACHING=false
```

### Development Environment

```bash
# Development .env
OPENAI_API_KEY=sk-dev-key-here
ANTHROPIC_API_KEY=sk-ant-dev-key-here
DEFAULT_PROVIDER=anthropic
LOG_LEVEL=DEBUG
ENABLE_AUDIT_LOGGING=false
MAX_CONCURRENT_ITEMS=3
REQUEST_TIMEOUT=15
ENABLE_MOCK_FALLBACK=true
```

## Configuration Validation

### Automatic Validation

The system automatically validates configuration on startup:

```python
from src.llm_judge.infrastructure.config.config import load_config, validate_config

try:
    config = load_config()
    validate_config(config)
    print("Configuration is valid")
except ConfigurationError as e:
    print(f"Configuration error: {e}")
    print("Please check your configuration file or environment variables")
```

### Manual Validation

```python
from src.llm_judge.infrastructure.config.config import LLMConfig

config = LLMConfig(
    openai_api_key="sk-test",
    anthropic_api_key="sk-ant-test",
    default_provider="invalid_provider"  # This will cause validation error
)

try:
    config.validate()
except ValueError as e:
    print(f"Invalid configuration: {e}")
```

### Common Configuration Issues

1. **Missing API Keys**: Ensure API keys are set in environment or config file
2. **Invalid Provider**: `default_provider` must be "openai" or "anthropic"
3. **Timeout Values**: Timeouts must be positive integers
4. **Batch Concurrency**: `max_concurrent_items` should be reasonable (1-50)
5. **Criteria Weights**: If validation enabled, weights should sum to 1.0
6. **Model Names**: Use valid model identifiers for each provider

## Configuration Priority Order

Configuration values are loaded in this priority order (highest to lowest):

1. **CLI Arguments**: `--provider anthropic --judge-model claude-3`
2. **Environment Variables**: `DEFAULT_PROVIDER=anthropic`
3. **Configuration File**: Values from `--config config.json`
4. **`.env` File**: Values from `.env` in project root
5. **System Environment**: System-wide environment variables
6. **Default Values**: Built-in defaults

### Example Priority Resolution

```bash
# .env file
DEFAULT_PROVIDER=openai

# config.json
{"default_provider": "anthropic"}

# CLI command
python -m src.llm_judge --provider openai evaluate "Question" "Answer"

# Result: Uses "openai" (CLI argument has highest priority)
```

## Monitoring and Debugging Configuration

### Configuration Logging

Enable configuration logging:

```bash
LOG_LEVEL=DEBUG python -m src.llm_judge evaluate "Question" "Answer"
```

Output shows configuration loading:

```
DEBUG: Loading configuration from environment
DEBUG: Found API key for provider: anthropic
DEBUG: Using default provider: anthropic
DEBUG: Configuration validation passed
INFO: LLM Judge initialized with provider: anthropic, model: claude-sonnet-4-20250514
```

### Configuration Inspection

```python
from src.llm_judge import LLMJudge

judge = LLMJudge()

# Inspect current configuration
config = judge.config
print(f"Provider: {config.default_provider}")
print(f"Model: {config.anthropic_model if config.default_provider == 'anthropic' else config.openai_model}")
print(f"Timeout: {config.request_timeout}")
print(f"Max Retries: {config.max_retries}")
```

### Health Check

```bash
# Test configuration
python -c "
from src.llm_judge import LLMJudge
import asyncio

async def health_check():
    try:
        judge = LLMJudge()
        print(f'✅ Configuration loaded successfully')
        print(f'Provider: {judge.config.default_provider}')
        print(f'Model: {judge.judge_model}')
        await judge.close()
    except Exception as e:
        print(f'❌ Configuration error: {e}')

asyncio.run(health_check())
"
```

## Best Practices

### Security

1. **Never commit API keys** to version control
2. **Use environment variables** for sensitive configuration
3. **Rotate API keys** regularly
4. **Limit API key permissions** when possible
5. **Use separate keys** for different environments

### Performance

1. **Tune concurrency** based on API rate limits
2. **Enable caching** for repeated evaluations
3. **Adjust timeouts** based on expected response times
4. **Monitor API usage** to optimize costs
5. **Use appropriate models** for your use case

### Reliability

1. **Configure retries** appropriately for your environment
2. **Enable fallback providers** for critical applications
3. **Set reasonable timeouts** to avoid hanging requests
4. **Enable audit logging** for production systems
5. **Test configuration** in staging before production deployment

### Cost Management

1. **Choose appropriate models** (GPT-3.5 vs GPT-4)
2. **Limit max_tokens** for cost control
3. **Use caching** to avoid duplicate API calls
4. **Monitor usage** with audit logging
5. **Consider batch processing** for efficiency
