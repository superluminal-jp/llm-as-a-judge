# Configuration Guide

This guide covers all configuration options for the LLM-as-a-Judge system.

## 🚀 Quick Start

### Basic Configuration

1. **Create Environment File**

   ```bash
   cp .env.example .env
   ```

2. **Add API Keys**

   ```bash
   # Edit .env file
   OPENAI_API_KEY=your-openai-api-key-here
   ANTHROPIC_API_KEY=your-anthropic-api-key-here
   DEFAULT_PROVIDER=anthropic
   ```

3. **Test Configuration**
   ```bash
   python -m src.llm_judge evaluate "Test" "Test response"
   ```

## 📚 Configuration Methods

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
USE_EQUAL_WEIGHTS=true
```

### 2. Configuration File (JSON)

Create `config.json`:

```json
{
  "default_provider": "anthropic",
  "openai_model": "gpt-5-2025-08-07",
  "anthropic_model": "claude-sonnet-4-20250514",
  "bedrock_model": "us.anthropic.claude-sonnet-4-20250514-v1:0",
  "request_timeout": 30,
  "connect_timeout": 10,
  "max_retries": 3,
  "retry_delay": 1,
  "log_level": "INFO",
  "dev_mode": false,
  "default_criteria_type": "default",
  "use_equal_weights": false,
  "persistence": {
    "enabled": false,
    "storage_type": "file",
    "storage_path": "./evaluation_cache.db"
  },
  "evaluation": {
    "default_scale_min": 1,
    "default_scale_max": 5,
    "normalize_weights": true,
    "minimum_criteria": 1
  }
}
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
    use_equal_weights=True,

    # Logging
    log_level="INFO",
    enable_audit_logging=True
)

judge = LLMJudge(config=config)
```

## ⚙️ Configuration Options

### Criteria Configuration

The system now supports flexible criteria configuration through the `criteria/` directory:

#### Criteria Directory Structure

```
criteria/
├── README.md                    # Criteria documentation
├── default.json                 # Default evaluation criteria
├── custom.json                  # Custom criteria example
└── template.json                # Template for creating new criteria
```

#### Criteria File Format

```json
{
  "name": "Criteria Set Name",
  "description": "Description of the criteria set",
  "criteria": [
    {
      "name": "criterion_name",
      "description": "What this criterion measures",
      "weight": 0.5,
      "evaluation_prompt": "Specific prompt for the LLM judge",
      "examples": {
        "1": "Poor example",
        "5": "Excellent example"
      },
      "domain_specific": false,
      "requires_context": false,
      "metadata": {
        "importance": "high",
        "category": "content_quality",
        "tags": ["tag1", "tag2"]
      }
    }
  ]
}
```

#### Configuration Options

| Parameter               | Type | Default   | Description                              |
| ----------------------- | ---- | --------- | ---------------------------------------- |
| `default_criteria_type` | str  | "default" | Default criteria type to use             |
| `use_equal_weights`     | bool | false     | Use equal weights for all criteria       |
| `normalize_weights`     | bool | true      | Normalize criteria weights to sum to 1.0 |
| `minimum_criteria`      | int  | 1         | Minimum number of criteria required      |

### LLM Provider Configuration

#### OpenAI Settings

| Parameter            | Type  | Default | Description                         |
| -------------------- | ----- | ------- | ----------------------------------- |
| `openai_api_key`     | str   | None    | OpenAI API key                      |
| `openai_model`       | str   | "gpt-4" | OpenAI model to use                 |
| `openai_max_tokens`  | int   | 4000    | Maximum tokens per request          |
| `openai_temperature` | float | 0.1     | Temperature for response generation |

#### Anthropic Settings

| Parameter               | Type  | Default                    | Description                         |
| ----------------------- | ----- | -------------------------- | ----------------------------------- |
| `anthropic_api_key`     | str   | None                       | Anthropic API key                   |
| `anthropic_model`       | str   | "claude-sonnet-4-20250514" | Anthropic model to use              |
| `anthropic_max_tokens`  | int   | 4000                       | Maximum tokens per request          |
| `anthropic_temperature` | float | 0.1                        | Temperature for response generation |

### Multi-Criteria Evaluation Settings

| Parameter                          | Type | Default         | Description                                                              |
| ---------------------------------- | ---- | --------------- | ------------------------------------------------------------------------ |
| `enable_multi_criteria_by_default` | bool | True            | Use multi-criteria evaluation by default                                 |
| `default_criteria_set`             | str  | "comprehensive" | Default criteria set ("comprehensive", "basic", "technical", "creative") |
| `multi_criteria_timeout`           | int  | 60              | Timeout for multi-criteria evaluation (seconds)                          |
| `fallback_on_parsing_error`        | bool | True            | Fallback to mock evaluation on JSON parsing errors                       |
| `use_equal_weights`                | bool | True            | Use equal weights for all criteria by default                            |

### Request and Timeout Settings

| Parameter              | Type  | Default | Description                    |
| ---------------------- | ----- | ------- | ------------------------------ |
| `request_timeout`      | int   | 30      | HTTP request timeout (seconds) |
| `connect_timeout`      | int   | 10      | Connection timeout (seconds)   |
| `max_retries`          | int   | 3       | Maximum retry attempts         |
| `retry_backoff_factor` | float | 2.0     | Exponential backoff factor     |

### Logging Configuration

| Parameter              | Type | Default | Description                                 |
| ---------------------- | ---- | ------- | ------------------------------------------- |
| `log_level`            | str  | "INFO"  | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `enable_audit_logging` | bool | False   | Enable audit logging for evaluations        |
| `log_file`             | str  | None    | Log file path (None for console only)       |

## 🔧 Advanced Configuration

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
  }
}
```

## 🧪 Configuration Validation

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

## 🔍 Configuration Priority

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

## 🆘 Troubleshooting

### Common Configuration Issues

1. **Missing API Keys**: Ensure API keys are set in environment or config file
2. **Invalid Provider**: `default_provider` must be "openai" or "anthropic"
3. **Timeout Values**: Timeouts must be positive integers
4. **Batch Concurrency**: `max_concurrent_items` should be reasonable (1-50)
5. **Model Names**: Use valid model identifiers for each provider

### Configuration Health Check

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

## 📚 Next Steps

- **[Environment Setup](environment.md)** - Detailed environment configuration
- **[Advanced Configuration](advanced.md)** - Advanced configuration options
- **[API Reference](../api/README.md)** - Complete API documentation
- **[Getting Started](../getting-started/README.md)** - Quick start guide
