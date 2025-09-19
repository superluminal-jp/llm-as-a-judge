# LLM-as-a-Judge System

[![Tests](https://img.shields.io/badge/tests-359%20passing-brightgreen)](https://github.com/superluminal-jp/llm-as-a-judge)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Architecture](https://img.shields.io/badge/architecture-DDD%20Clean%20Architecture-purple)](docs/architecture/README.md)

A comprehensive LLM-as-a-Judge system for evaluating language model outputs with **multi-criteria evaluation by default**. Features comprehensive scoring across 7 evaluation dimensions with rich CLI interface, robust batch processing capabilities, and **structured output support** across all providers.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment (optional - for real LLM integration)
cp .env.example .env
# Edit .env with your API keys

# CLI Usage - Multi-criteria evaluation (default)
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence"

# CLI Usage - Custom criteria weights
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence" --criteria-weights "accuracy:0.4,clarity:0.3,helpfulness:0.3"

# CLI Usage - Equal weights for all criteria (now the default)
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence" --equal-weights

# CLI Usage - Custom criteria definition
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence" --custom-criteria "accuracy:Factual correctness:factual:0.4,clarity:How clear the response is:linguistic:0.3,helpfulness:How useful the response is:qualitative:0.3"

# CLI Usage - Custom criteria from file
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence" --criteria-file criteria/default.json

# CLI Usage - List available criteria types
python -m src.llm_judge evaluate --list-criteria-types

# CLI Usage - Create criteria template
python -m src.llm_judge create-criteria-template my-criteria.json --name "Academic Evaluation" --description "Criteria for academic content"

# CLI Usage - Data management
python -m src.llm_judge data list --limit 10 --format table
python -m src.llm_judge data export results.json --limit 100
python -m src.llm_judge data clean-cache --force

# CLI Usage - Single-criterion evaluation (legacy)
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence" --single-criterion --criteria "accuracy"

# CLI Usage - Compare two responses
python -m src.llm_judge compare "Explain ML" "Basic explanation" "Detailed explanation" --model-a gpt-4 --model-b claude-3

# CLI Usage - Batch processing from file
python -m src.llm_judge create-sample-batch sample.jsonl  # Create sample file
python -m src.llm_judge batch sample.jsonl --output results.json --max-concurrent 5

# Run tests
pytest

# Run specific test suites
pytest tests/unit/                    # Unit tests only
pytest tests/integration/             # Integration tests only
pytest tests/unit/infrastructure/     # Infrastructure layer tests
```

## 📖 Documentation

### 🎯 For Different Audiences

| **I want to...**          | **Start here**                                      | **Then explore**                              |
| ------------------------- | --------------------------------------------------- | --------------------------------------------- |
| **Get started quickly**   | [Quick Start Guide](docs/getting-started/README.md) | [Configuration](docs/configuration/README.md) |
| **Understand the system** | [System Overview](docs/overview/README.md)          | [Architecture](docs/architecture/README.md)   |
| **Use the API**           | [API Reference](docs/api/README.md)                 | [Examples](docs/examples/README.md)           |
| **Develop features**      | [Development Guide](docs/development/README.md)     | [Testing](docs/testing/README.md)             |
| **Deploy/Operate**        | [Deployment Guide](docs/deployment/README.md)       | [Configuration](docs/configuration/README.md) |

### 📚 Complete Documentation Structure

```
docs/
├── getting-started/          # 🚀 Quick start and basic usage
│   ├── README.md            # Quick start guide
│   ├── installation.md      # Installation instructions
│   └── first-steps.md       # Your first evaluation
├── overview/                # 🎯 System overview and concepts
│   ├── README.md            # System overview
│   ├── features.md          # Key features and capabilities
│   └── concepts.md          # Core concepts and terminology
├── api/                     # 📖 API documentation
│   ├── README.md            # API overview
│   ├── reference.md         # Complete API reference
│   └── examples.md          # Code examples and patterns
├── configuration/           # ⚙️ Configuration and setup
│   ├── README.md            # Configuration overview
│   ├── environment.md       # Environment setup
│   └── advanced.md          # Advanced configuration
├── architecture/            # 🏗️ System architecture
│   ├── README.md            # Architecture overview
│   ├── design.md            # Design principles and patterns
│   └── components.md        # Component details
├── development/             # 👨‍💻 Development guides
│   ├── README.md            # Development overview
│   ├── setup.md             # Development environment
│   ├── contributing.md      # Contributing guidelines
│   └── code-standards.md    # Coding standards
├── testing/                 # 🧪 Testing documentation
│   ├── README.md            # Testing overview
│   ├── running-tests.md     # How to run tests
│   └── writing-tests.md     # How to write tests
├── deployment/              # 🚀 Deployment and operations
│   ├── README.md            # Deployment overview
│   ├── production.md        # Production deployment
│   └── monitoring.md        # Monitoring and observability
└── examples/                # 💡 Examples and tutorials
    ├── README.md            # Examples overview
    ├── basic-usage.md       # Basic usage examples
    ├── advanced-usage.md    # Advanced usage examples
    └── integration.md       # Integration examples
```

## 🏗️ Project Structure

The project follows Domain-Driven Design (DDD) principles with clean architecture:

```
llm-as-a-judge/
├── src/llm_judge/                    # Main application package
│   ├── __init__.py                  # Package exports (LLMJudge, CandidateResponse, etc.)
│   ├── __main__.py                  # CLI entry point
│   ├── domain/                      # Business logic and domain models
│   │   ├── evaluation/              # Multi-criteria evaluation domain logic
│   │   ├── batch/                   # Batch processing domain logic
│   │   └── models/                  # Domain models and value objects
│   ├── application/                 # Use cases and application services
│   │   ├── services/                # Application services
│   │   └── use_cases/               # Specific use case implementations
│   ├── infrastructure/              # External concerns and technical details
│   │   ├── clients/                 # LLM provider API clients
│   │   ├── config/                  # Configuration management
│   │   ├── resilience/              # Reliability and resilience patterns
│   │   └── logging/                 # Logging infrastructure
│   └── presentation/                # User interfaces
│       └── cli/                     # Command-line interface
├── tests/                           # Test suite organized by layer
│   ├── unit/                        # Unit tests (isolated, fast)
│   ├── integration/                 # Integration tests (cross-layer)
│   └── fixtures/                    # Test fixtures and sample data
├── docs/                            # Comprehensive documentation
├── criteria/                        # Evaluation criteria configuration files
├── config.json                      # Main configuration file
└── README.md                        # This file - project overview
```

## 🎯 Key Features

### ✅ Multi-Criteria Evaluation (Default)

- **7 evaluation criteria**: accuracy, completeness, clarity, relevance, helpfulness, coherence, appropriateness
- **Weighted scoring system**: Configurable weights for each criterion
- **Rich statistical analysis**: Mean, median, standard deviation, confidence intervals
- **Detailed qualitative feedback**: Strengths, weaknesses, and improvement suggestions

### ✅ Advanced Display Capabilities

- **Rich CLI formatting**: Beautiful tables with Rich library integration
- **Comprehensive JSON output**: Structured data with all criterion details
- **Progress indicators**: Real-time feedback during evaluation processing
- **Score visualization**: Color-coded scoring and percentage displays

### ✅ Flexible Evaluation Modes

- **Multi-criteria by default**: Comprehensive 7-dimension analysis
- **Single-criterion mode**: Backward compatible with `--single-criterion` flag
- **Custom criteria support**: Adapt to different evaluation contexts
- **Batch multi-criteria**: All batch operations use comprehensive evaluation

### ✅ Structured Output Support

- **Provider-native structured output**: Uses each provider's JSON schema capabilities
- **Guaranteed response format**: Consistent JSON structure across all providers
- **Intelligent fallback parsing**: Handles parsing errors with sentiment analysis
- **Type-safe validation**: Enforces proper data types and value ranges

## 🎯 Current Status

### ✅ Phase 2 Complete: Production-Ready Foundation

- ✅ **Real LLM API integration** (OpenAI GPT-4, Anthropic Claude)
- ✅ **Robust error handling** and retry logic with circuit breakers
- ✅ **Configuration management** with hierarchical loading
- ✅ **Timeout management** and request cancellation
- ✅ **Fallback mechanisms** and degraded service modes
- ✅ **Complete test suite** - 236/236 tests passing
- ✅ **Enhanced resilience patterns** and error classification
- ✅ **Comprehensive CLI interface** with evaluation and comparison commands

### ✅ Phase 3 Complete: Advanced Features

- ✅ **Multi-criteria evaluation by default**: Comprehensive 7-dimension analysis
- ✅ **Advanced batch processing**: Multi-criteria evaluation in batch operations
- ✅ **Rich CLI interface**: Beautiful formatted output with tables and progress indicators
- ✅ **Robust JSON parsing**: Multiple fallback strategies for reliable LLM response processing
- ✅ **Comprehensive error handling**: Validation, fallbacks, and graceful degradation
- ✅ **Multi-format file support**: JSONL, CSV, JSON with intelligent parsing
- ✅ **Domain-driven evaluation models**: Proper separation of criteria, scoring, and result aggregation

## 🧪 Testing

**🎉 ALL 236 TESTS PASSING - Complete Test Suite Reliability**

```bash
# Run all tests (236/236 passing)
pytest

# Run specific test suites
pytest tests/unit/                    # Unit tests only
pytest tests/integration/             # Integration tests only
pytest tests/unit/infrastructure/     # Infrastructure layer tests

# Run with coverage
pytest --cov=src/llm_judge --cov-report=html
```

## 🚀 Usage Examples

### Basic Multi-Criteria Evaluation

```python
from src.llm_judge import LLMJudge, CandidateResponse
import asyncio

async def basic_evaluation():
judge = LLMJudge()

candidate = CandidateResponse(
    prompt="What is AI?",
    response="AI is artificial intelligence",
    model="gpt-4"
)

    # Multi-criteria evaluation (default)
    result = await judge.evaluate_multi_criteria(candidate)

    print(f"Overall Score: {result.aggregated.overall_score:.1f}/5")
    print(f"Criteria Count: {len(result.criterion_scores)}")

    # Access individual criterion scores
    for cs in result.criterion_scores:
    print(f"{cs.criterion_name}: {cs.score}/5 - {cs.reasoning}")

    await judge.close()

asyncio.run(basic_evaluation())
```

### Pairwise Comparison

```python
async def compare_responses():
    judge = LLMJudge()

candidate_a = CandidateResponse(
    prompt="Explain quantum computing",
    response="Quantum computing uses quantum bits in superposition.",
    model="gpt-4"
)

candidate_b = CandidateResponse(
    prompt="Explain quantum computing",
    response="Quantum computers leverage quantum phenomena like superposition and entanglement.",
    model="claude-3"
)

    # Compare responses
result = await judge.compare_responses(candidate_a, candidate_b)
print(f"Winner: {result['winner']}")           # 'A', 'B', or 'tie'
print(f"Reasoning: {result['reasoning']}")     # Detailed comparison analysis
print(f"Confidence: {result['confidence']}")   # Confidence score 0-1

await judge.close()

asyncio.run(compare_responses())
```

## 🔧 Configuration

### Criteria Configuration

The system now uses a unified criteria configuration system with the `criteria/` directory:

```
criteria/
├── README.md                    # Criteria documentation
├── default.json                 # Default evaluation criteria
├── custom.json                  # Custom criteria example
└── template.json                # Template for creating new criteria
```

### Environment Configuration

Create a `.env` file in the project root:

```bash
# LLM Provider API Keys
OPENAI_API_KEY=your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# Default Provider (openai or anthropic)
DEFAULT_PROVIDER=anthropic

# Model Configuration
OPENAI_MODEL=gpt-4
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# Timeout Configuration (seconds)
REQUEST_TIMEOUT=30
CONNECT_TIMEOUT=10

# Logging Level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
```

## 🤝 Contributing

This project follows a structured development approach based on Domain-Driven Design:

1. **Documentation-First**: Review planning docs in `docs/` before coding
2. **Layer Separation**: Respect the DDD architecture boundaries
3. **Test-Driven**: Write tests before implementation
4. **Incremental**: Small, working increments with rollback capability

See [Development Guide](docs/development/README.md) for detailed contributing guidelines.

## 📄 License

MIT License - Open source implementation following the Evidently AI methodology.

## 🙏 Acknowledgments

- [Evidently AI](https://www.evidentlyai.com/) for the LLM-as-a-Judge methodology
- OpenAI and Anthropic for LLM APIs
- The Domain-Driven Design community for architectural guidance
- The open-source community for tools and inspiration

---

**Need help?** Check out our [documentation](docs/) or [open an issue](https://github.com/superluminal-jp/llm-as-a-judge/issues).
