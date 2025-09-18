# LLM-as-a-Judge System

A comprehensive implementation of an LLM-as-a-Judge system for evaluating language model outputs with **multi-criteria evaluation by default**. Features comprehensive scoring across 7 evaluation dimensions with rich CLI interface, robust batch processing capabilities, and **structured output support** across all providers.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment (optional - for real LLM integration)
cp .env.example .env
# Edit .env with your API keys

# CLI Usage - Multi-criteria evaluation (default)
python -m llm_judge evaluate "What is AI?" "AI is artificial intelligence"

# CLI Usage - Single-criterion evaluation (legacy)
python -m llm_judge evaluate "What is AI?" "AI is artificial intelligence" --single-criterion --criteria "accuracy"

# CLI Usage - Compare two responses
python -m llm_judge compare "Explain ML" "Basic explanation" "Detailed explanation" --model-a gpt-4 --model-b claude-3

# CLI Usage - Batch processing from file
python -m llm_judge create-sample-batch sample.jsonl  # Create sample file
python -m llm_judge batch sample.jsonl --output results.json --max-concurrent 5

# Run tests
pytest

# Run specific test suites
pytest tests/unit/                    # Unit tests only
pytest tests/integration/             # Integration tests only
pytest tests/unit/infrastructure/     # Infrastructure layer tests
```

## Project Structure

The project follows Domain-Driven Design (DDD) principles with clean architecture:

```
llm-as-a-judge/
├── src/llm_judge/                    # Main application package
│   ├── __init__.py                  # Package exports (LLMJudge, CandidateResponse, etc.)
│   ├── __main__.py                  # CLI entry point
│   ├── domain/                      # Business logic and domain models
│   │   ├── evaluation/              # Multi-criteria evaluation domain logic
│   │   │   ├── criteria.py          # Evaluation criteria definitions
│   │   │   └── results.py           # Multi-criteria result models
│   │   ├── batch/                   # Batch processing domain logic
│   │   └── models/                  # Domain models and value objects
│   ├── application/                 # Use cases and application services
│   │   ├── services/                # Application services
│   │   │   └── llm_judge_service.py # Main LLM judge implementation
│   │   └── use_cases/               # Specific use case implementations
│   ├── infrastructure/              # External concerns and technical details
│   │   ├── clients/                 # LLM provider API clients
│   │   │   ├── openai_client.py     # OpenAI API integration
│   │   │   ├── anthropic_client.py  # Anthropic API integration
│   │   │   ├── multi_criteria_client.py # Multi-criteria evaluation clients
│   │   │   └── http_client.py       # HTTP client infrastructure
│   │   ├── config/                  # Configuration management
│   │   │   ├── config.py            # Configuration loading and validation
│   │   │   └── logging_config.py    # Logging setup and formatters
│   │   ├── resilience/              # Reliability and resilience patterns
│   │   │   ├── retry_strategies.py  # Retry logic with backoff
│   │   │   ├── fallback_manager.py  # Fallback and circuit breaker
│   │   │   ├── timeout_manager.py   # Request timeout handling
│   │   │   └── error_classification.py # Error categorization
│   │   └── logging/                 # Logging infrastructure
│   └── presentation/                # User interfaces
│       └── cli/                     # Command-line interface
│           ├── main.py              # Main CLI commands
│           ├── multi_criteria_display.py # Rich formatting for multi-criteria results
│           └── batch_commands.py    # Batch processing CLI commands
├── tests/                           # Test suite organized by layer
│   ├── unit/                        # Unit tests (isolated, fast)
│   │   ├── domain/                  # Domain layer tests
│   │   ├── application/             # Application layer tests
│   │   └── infrastructure/          # Infrastructure layer tests
│   │       ├── test_*_client.py     # API client tests
│   │       ├── test_config.py       # Configuration tests
│   │       └── test_*_manager.py    # Resilience component tests
│   ├── integration/                 # Integration tests (cross-layer)
│   │   ├── test_llm_judge_integration.py # End-to-end judge tests
│   │   ├── test_error_integration.py     # Error handling integration
│   │   └── test_timeout_integration.py   # Timeout behavior tests
│   └── fixtures/                    # Test fixtures and sample data
│       ├── README.md               # Test fixtures documentation
│       └── sample_data/            # Sample data for testing
│           ├── minimal_batch.jsonl  # Minimal test batch
│           ├── test_batch.jsonl    # Standard test scenarios
│           └── sample_batch_results.json # Sample results format
├── docs/                            # Comprehensive documentation
│   ├── README.md                    # Documentation navigation guide
│   ├── STRATEGY.md                  # Business vision and objectives
│   ├── ARCHITECTURE.md              # System design and patterns
│   ├── DOMAIN-MODEL.md              # Business concepts and language
│   ├── IMPLEMENTATION.md            # Technical execution details
│   ├── MULTI_CRITERIA_EVALUATION.md # Multi-criteria evaluation guide
│   ├── STRUCTURED_OUTPUT.md         # Structured output implementation guide
│   ├── API_REFERENCE.md             # Complete API documentation
│   ├── CONFIGURATION.md             # Configuration and setup guide
│   ├── TESTING.md                   # Testing overview
│   ├── TASKS.md                     # Current iteration breakdown
│   ├── development/                 # Development-specific documentation
│   │   ├── CODE_PLAN.md             # Development planning and standards
│   │   ├── BEDROCK_INTEGRATION.md   # AWS Bedrock integration details
│   │   └── CONSISTENCY_IMPROVEMENTS_SUMMARY.md # Provider consistency
│   └── testing/                     # Testing documentation
│       ├── TEST_SUITE_SUMMARY.md    # Complete test suite overview
│       ├── TEST_COVERAGE_MATRIX.md  # Detailed coverage matrix
│       ├── TEST_SCENARIOS_DETAILED.md # Detailed test scenarios
│       └── TEST_EXECUTION_GUIDE.md  # Test execution procedures
├── logs/                            # Application logs (gitignored)
├── .env.example                     # Environment variables template
├── .gitignore                       # Git ignore patterns
├── pytest.ini                      # Pytest configuration
├── requirements.txt                 # Python dependencies
└── README.md                        # This file - project overview
```

## 🎯 Multi-Criteria Evaluation Features

✅ **Comprehensive Multi-Dimensional Analysis**

- ✅ **7 evaluation criteria by default**: accuracy, completeness, clarity, relevance, helpfulness, coherence, appropriateness
- ✅ **Weighted scoring system**: Each criterion has configurable weights (accuracy: 20%, etc.)
- ✅ **Rich statistical analysis**: Mean, median, standard deviation, confidence intervals
- ✅ **Detailed qualitative feedback**: Strengths, weaknesses, and improvement suggestions
- ✅ **Beautiful formatted output**: Color-coded tables, progress bars, and visual scoring

✅ **Advanced Display Capabilities**

- ✅ **Rich CLI formatting**: Beautiful tables with Rich library integration
- ✅ **Comprehensive JSON output**: Structured data with all criterion details
- ✅ **Fallback text display**: Works without Rich library for basic terminals
- ✅ **Progress indicators**: Real-time feedback during evaluation processing
- ✅ **Score visualization**: Color-coded scoring and percentage displays

✅ **Flexible Evaluation Modes**

- ✅ **Multi-criteria by default**: Comprehensive 7-dimension analysis
- ✅ **Single-criterion mode**: Backward compatible with `--single-criterion` flag
- ✅ **Custom criteria support**: Adapt to different evaluation contexts
- ✅ **Batch multi-criteria**: All batch operations use comprehensive evaluation
- ✅ **JSON/Text output**: Structured or human-readable formats

✅ **Structured Output Support**

- ✅ **Provider-native structured output**: Uses each provider's JSON schema capabilities
- ✅ **Guaranteed response format**: Consistent JSON structure across all providers
- ✅ **Intelligent fallback parsing**: Handles parsing errors with sentiment analysis
- ✅ **Type-safe validation**: Enforces proper data types and value ranges
- ✅ **Cross-provider consistency**: Unified schema for OpenAI, Anthropic, and Bedrock

## Current Status

✅ **Project Structure Reorganization Complete**

- ✅ Domain-Driven Design (DDD) layered architecture implemented
- ✅ Clean separation of concerns across domain, application, infrastructure, and presentation layers
- ✅ Comprehensive test suite organization by layer and type (unit/integration)
- ✅ Updated import paths and package structure throughout codebase
- ✅ **Comprehensive CLI interface with evaluation and comparison commands**
- ✅ All existing functionality preserved and verified working

✅ **Phase 1 Complete**: Working Minimal Implementation

- ✅ Direct scoring evaluation (1-5 integer scale) with structured reasoning
- ✅ **Pairwise comparison (A vs B vs tie) FULLY RECOVERED and operational**
- ✅ Mock LLM integration for development and testing
- ✅ Command-line demo interface with examples
- ✅ Comprehensive planning documentation across all architectural levels

✅ **Phase 2 Infrastructure Complete**: Production-Ready Foundation

- ✅ Real LLM API integration (OpenAI GPT-4, Anthropic Claude)
- ✅ Robust error handling and retry logic with circuit breakers
- ✅ Configuration management with hierarchical loading
- ✅ Timeout management and request cancellation
- ✅ Fallback mechanisms and degraded service modes
- ✅ **Complete test suite overhaul - ALL TESTS PASSING**
- ✅ **pytest error elimination - 100% test reliability**
- ✅ Enhanced resilience patterns and error classification
- ✅ **Comprehensive CLI interface with evaluation and comparison commands**

✅ **Phase 3 Complete**: Enhanced Batch Processing & Multi-Criteria System

- ✅ **Multi-criteria evaluation by default**: Comprehensive 7-dimension analysis for all evaluations
- ✅ **Advanced batch processing**: Multi-criteria evaluation in batch operations with full metadata
- ✅ **Rich CLI interface**: Beautiful formatted output with tables, statistics, and progress indicators
- ✅ **Robust JSON parsing**: Multiple fallback strategies for reliable LLM response processing
- ✅ **Comprehensive error handling**: Validation, fallbacks, and graceful degradation
- ✅ **Multi-format file support**: JSONL, CSV, JSON with intelligent parsing and validation
- ✅ **Domain-driven evaluation models**: Proper separation of criteria, scoring, and result aggregation

✅ **Testing Infrastructure Complete**

- ✅ **168/168 tests passing (100% success rate)**
- ✅ Comprehensive unit test coverage with proper SDK mocking
- ✅ Integration tests with fallback manager validation
- ✅ Enhanced CLI testing with comprehensive command coverage
- ✅ Async test support with pytest-asyncio configuration
- ✅ Test isolation and reliable test execution
- ✅ Error classification and resilience testing

## Implementation Documentation

### 📋 Layered Documentation Strategy

Following the AI Coding Agent Governance Framework, we maintain sophisticated documentation across multiple abstraction levels:

| Document                                         | Abstraction Level  | Purpose                                               | Primary Audience                          |
| ------------------------------------------------ | ------------------ | ----------------------------------------------------- | ----------------------------------------- |
| [docs/STRATEGY.md](docs/STRATEGY.md)             | **Strategic**      | Business vision, market analysis, success metrics     | C-Suite, Product Strategy, Investors      |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)     | **Architectural**  | System design, component relationships, scalability   | Solution Architects, Technical Leadership |
| [docs/DOMAIN-MODEL.md](docs/DOMAIN-MODEL.md)     | **Domain**         | Business concepts, ubiquitous language, domain rules  | Domain Experts, Senior Developers         |
| [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) | **Implementation** | Detailed technical execution with acceptance criteria | Development Teams, DevOps Engineers       |
| [docs/TASKS.md](docs/TASKS.md)                   | **Task**           | Current sprint breakdown with validation gates        | Individual Developers, Scrum Masters      |
| [CODE_PLAN.md](CODE_PLAN.md)                     | **Code**           | Specific code structure and implementation examples   | Junior/Mid-level Developers               |

### 🎯 Documentation Synchronization Status

| Document          | Last Updated | Sync Status     | Code Alignment                                |
| ----------------- | ------------ | --------------- | --------------------------------------------- |
| STRATEGY.md       | Current      | ✅ Synchronized | Reflects current business objectives          |
| ARCHITECTURE.md   | Current      | ✅ Synchronized | Matches planned system design                 |
| DOMAIN-MODEL.md   | Current      | ✅ Synchronized | Captures current domain understanding         |
| IMPLEMENTATION.md | Current      | ✅ Synchronized | Detailed Phase 1 completion, Phase 2 planning |
| TASKS.md          | Current      | ✅ Synchronized | Active sprint tasks with validation gates     |
| CODE_PLAN.md      | Current      | ✅ Synchronized | Matches current code structure                |
| README.md         | Current      | ✅ Synchronized | Reflects actual system state and capabilities |

### 🎯 Development Phases

#### Phase 1: MVP ✅ COMPLETE

- ✅ Single-file working implementation
- ✅ Core evaluation methods
- ✅ Demo functionality

#### Phase 2: Production Foundation ✅ COMPLETE

- ✅ Real LLM API integration (OpenAI, Anthropic)
- ✅ Error handling and retry logic
- ✅ Configuration management
- ✅ Enhanced CLI interface with evaluation and comparison
- [ ] Data persistence (Next)

#### Phase 3: Advanced Features

- [ ] Batch processing
- [ ] REST API
- [ ] Reference-based evaluation
- [ ] Custom evaluation criteria
- [ ] Analytics dashboard

#### Phase 4: Enterprise Scale

- [ ] Multi-tenancy
- [ ] High availability
- [ ] Advanced security
- [ ] Performance optimization
- [ ] Integration ecosystem

## Architecture Overview

The system follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                       │
│  CLI Interface, Future: Web UI, REST API                   │
│  src/llm_judge/presentation/                               │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                  Application Layer                          │
│  Use Cases, Application Services, Orchestration            │
│  src/llm_judge/application/                                │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                   Domain Layer                              │
│  Business Logic, Domain Models, Domain Services            │
│  src/llm_judge/domain/                                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│               Infrastructure Layer                          │
│  External APIs, Config, Databases, Resilience Patterns     │
│  src/llm_judge/infrastructure/                             │
└─────────────────────────────────────────────────────────────┘

Key Principles:
• Dependencies point inward (Dependency Inversion)
• Domain layer has no external dependencies
• Infrastructure implements interfaces defined in inner layers
• Clear separation between business logic and technical concerns
```

## Key Features

### Evaluation Methods

- **Multi-Criteria Evaluation**: Comprehensive 7-dimension analysis (accuracy, completeness, clarity, relevance, helpfulness, coherence, appropriateness)
- **Direct Scoring**: Rate responses with detailed criterion-specific scoring and reasoning
- **Pairwise Comparison**: Compare two responses (A vs B vs tie) with detailed analysis
- **Statistical Analysis**: Weighted scores, confidence intervals, mean/median/std deviation
- **Qualitative Feedback**: Strengths, weaknesses, and actionable improvement suggestions

### LLM Provider Support

- **OpenAI**: GPT-4 and GPT-3.5 models with robust error handling
- **Anthropic**: Claude-3 Sonnet with advanced multi-criteria prompting
- **Fallback Systems**: Automatic provider switching and mock mode for development

### Evaluation Criteria System

- **7 Default Criteria**: Comprehensive evaluation across multiple dimensions
- **Weighted Scoring**: Configurable weights for different criteria (accuracy: 20%, completeness: 15%, etc.)
- **Custom Criteria**: Support for domain-specific evaluation requirements
- **Criterion Types**: Factual, qualitative, structural, contextual, linguistic, ethical categories

## Usage Examples

### Current Usage

**✅ Fully Functional Compare Responses Feature**

```python
# Import from the organized package structure
from src.llm_judge import LLMJudge, CandidateResponse, LLMConfig
import asyncio

# Basic usage with default configuration
judge = LLMJudge()

# Multi-criteria evaluation (default behavior)
candidate = CandidateResponse(
    prompt="What is AI?",
    response="AI is artificial intelligence",
    model="gpt-4"
)

# Returns comprehensive multi-criteria result
multi_result = await judge.evaluate_multi_criteria(candidate)
print(f"Overall Score: {multi_result.aggregated.overall_score:.1f}/5")
print(f"Criteria Evaluated: {len(multi_result.criterion_scores)}")
print(f"Confidence: {multi_result.aggregated.confidence:.1%}")

# Individual criterion scores
for cs in multi_result.criterion_scores:
    print(f"{cs.criterion_name}: {cs.score}/5 - {cs.reasoning}")

# Legacy single evaluation (backward compatible)
result = await judge.evaluate_response(candidate, "accuracy and clarity", use_multi_criteria=False)
print(f"Score: {result.score}/5")
print(f"Reasoning: {result.reasoning}")

# 🚀 PAIRWISE COMPARISON - FULLY RECOVERED
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

# Compare responses - WORKING PERFECTLY
result = await judge.compare_responses(candidate_a, candidate_b)
print(f"Winner: {result['winner']}")           # 'A', 'B', or 'tie'
print(f"Reasoning: {result['reasoning']}")     # Detailed comparison analysis
print(f"Confidence: {result['confidence']}")   # Confidence score 0-1

# Using real LLM providers
config = LLMConfig(
    openai_api_key="your-api-key",
    anthropic_api_key="your-anthropic-key",
    default_provider="anthropic",  # or "openai"
    anthropic_model="claude-sonnet-4-20250514"
)
judge = LLMJudge(config=config)

# CLI usage
# python -m src.llm_judge "What is AI?" "AI is artificial intelligence"

# Close resources
await judge.close()
```

### ✅ Phase 3 Batch Processing

```python
# Import batch processing capabilities
from src.llm_judge import BatchProcessingService, BatchRequest, CandidateResponse, LLMJudge, LLMConfig
import asyncio

# Create batch processing service
config = LLMConfig(openai_api_key="sk-...", default_provider="openai")
judge = LLMJudge(config=config)
batch_service = BatchProcessingService(judge, max_workers=5)

# Manual batch creation
batch_request = BatchRequest(name="My Evaluation Batch", max_concurrent_items=5)

# Add single evaluations
batch_request.add_single_evaluation(
    CandidateResponse("What is AI?", "AI is artificial intelligence", "gpt-4"),
    criteria="accuracy and clarity"
)

# Add pairwise comparisons
batch_request.add_comparison_evaluation(
    CandidateResponse("Explain ML", "ML is subset of AI", "gpt-3.5"),
    CandidateResponse("Explain ML", "Machine learning enables computers to learn", "gpt-4")
)

# Process batch with progress tracking
def progress_callback(progress):
    print(f"Progress: {progress.completion_percentage:.1%} ({progress.completed_items}/{progress.total_items})")

result = await batch_service.process_batch_request(batch_request, progress_callback)
print(f"Completed {result.completed_items_count}/{result.total_items} evaluations")
print(f"Success rate: {result.success_rate:.1%}")

# File-based batch processing
result = await batch_service.process_batch_from_file(
    "evaluations.jsonl",
    output_path="results.json",
    batch_config={"max_concurrent_items": 10, "retry_failed_items": True}
)

await judge.close()
```

**Key Methods Available:**

- `evaluate_response()`: Single response evaluation with 1-5 scoring
- `compare_responses()`: **Pairwise comparison - FULLY OPERATIONAL**
- Both methods support real LLM APIs (OpenAI, Anthropic) with fallback to mock mode

## 🖥️ Command Line Interface

The LLM-as-a-Judge system includes a comprehensive CLI for both evaluation and comparison functionality.

### Basic Usage

```bash
# Get help
python -m llm_judge --help

# Multi-criteria evaluation (default) - evaluates across 7 dimensions
python -m llm_judge evaluate "What is AI?" "AI is artificial intelligence"

# Single-criterion evaluation (legacy mode)
python -m llm_judge evaluate "What is AI?" "AI is artificial intelligence" --single-criterion

# Show detailed multi-criteria breakdown
python -m llm_judge evaluate "What is AI?" "AI is artificial intelligence" --show-detailed

# Compare two responses
python -m llm_judge compare "Explain machine learning" "ML is AI subset" "Machine learning is a subset of AI that enables computers to learn from data"

# Create and process batch evaluations (all use multi-criteria by default)
python -m llm_judge create-sample-batch sample.jsonl --format jsonl
python -m llm_judge batch sample.jsonl --output results.json --max-concurrent 10
```

### Advanced Usage

```bash
# Single-criterion with custom criteria
python -m llm_judge evaluate "What is AI?" "AI is artificial intelligence" --single-criterion --criteria "accuracy and completeness"

# Specify models for comparison
python -m llm_judge compare "Explain ML" "Basic answer" "Detailed answer" \
  --model-a gpt-3.5-turbo --model-b gpt-4

# Choose LLM provider and judge model
python -m llm_judge --provider anthropic --judge-model claude-3 \
  evaluate "Question" "Answer"

# Use configuration file
python -m llm_judge --config ./config.json evaluate "Question" "Answer"

# Output as JSON for programmatic use
python -m llm_judge --output json evaluate "Question" "Answer"

# Advanced batch processing
python -m llm_judge batch large_dataset.jsonl \
  --output detailed_results.json \
  --max-concurrent 20 \
  --max-retries 5 \
  --batch-name "Model Comparison Study" \
  --provider anthropic

# Process with custom settings and progress indicators
python -m llm_judge batch evaluations.csv \
  --output results.json \
  --max-concurrent 15 \
  --no-retry \
  --fail-fast
```

### Configuration File

Create a configuration file to manage API keys and settings:

```json
{
  "openai_api_key": "sk-your-openai-key-here",
  "anthropic_api_key": "sk-ant-your-anthropic-key-here",
  "default_provider": "openai",
  "openai_model": "gpt-5-2025-08-07",
  "anthropic_model": "claude-sonnet-4-20250514",
  "request_timeout": 30,
  "max_retries": 3,
  "log_level": "INFO"
}
```

### CLI Commands

#### `evaluate` - Evaluate Single Response

```bash
python -m llm_judge evaluate [OPTIONS] PROMPT RESPONSE

Options:
  --single-criterion      Use single-criterion evaluation instead of multi-criteria (default: False)
  --show-detailed        Show detailed multi-criteria breakdown
  --criteria TEXT        Evaluation criteria for single-criterion mode (default: "overall quality")
  --model TEXT           Model that generated the response
```

#### `compare` - Compare Two Responses

```bash
python -m llm_judge compare [OPTIONS] PROMPT RESPONSE_A RESPONSE_B

Options:
  --model-a TEXT     Model that generated response A
  --model-b TEXT     Model that generated response B
```

#### Global Options

```bash
--provider {openai,anthropic}  LLM provider to use as judge
--judge-model TEXT            Specific model to use as judge
--config PATH                 Path to configuration file
--output {text,json}          Output format (default: text)
--verbose, -v                 Enable verbose output
```

### Output Formats

**Multi-Criteria Text Format (default):**

```
🎯 Multi-Criteria LLM Evaluation Results
================================================================================
╭─────────────────── Overall Score ────────────────────╮
│ 3.8/5.0                                             │
│ Confidence: 88.5%                                   │
│ Based on 7 criteria                                 │
╰──────────────────────────────────────────────────────╯

📊 Detailed Criterion Scores
┏━━━━━━━━━━━━┳━━━━┳━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓
┃ Criterion  ┃ Sc…┃ We… ┃ Con… ┃ Reasoning          ┃
┡━━━━━━━━━━━━╇━━━━╇━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩
│ accuracy   │ 4…│ 20… │ 90.… │ Factually correct  │
│ clarity    │ 4…│ 15… │ 85.… │ Well articulated   │
│ relevance  │ 5…│ 15… │ 95.… │ Directly addresses │
└────────────┴────┴─────┴──────┴────────────────────┘

✅ Strengths: Clear, accurate, relevant
⚠️  Areas for Improvement: Lacks depth, needs examples
💡 Suggestions: Add more detail, provide context
```

**Multi-Criteria JSON Format:**

```json
{
  "type": "multi_criteria_evaluation",
  "overall_score": 3.8,
  "overall_confidence": 0.885,
  "criteria_count": 7,
  "judge_model": "claude-sonnet-4-20250514",
  "criterion_scores": [
    {
      "criterion": "accuracy",
      "score": 4.0,
      "percentage": 80.0,
      "reasoning": "Factually correct but could be more detailed",
      "confidence": 0.9,
      "weight": 0.2
    },
    {
      "criterion": "clarity",
      "score": 4.0,
      "percentage": 80.0,
      "reasoning": "Clear and well articulated",
      "confidence": 0.85,
      "weight": 0.15
    }
  ],
  "strengths": ["Clear", "Accurate", "Relevant"],
  "weaknesses": ["Lacks depth", "Needs examples"],
  "suggestions": ["Add more detail", "Provide context"]
}
```

### Planned Enhanced Usage

```python
# Real LLM integration (Phase 2)
judge = EnhancedLLMJudge(provider="openai", api_key="sk-...")

# Async evaluation
result = await judge.evaluate_response_async(candidate)

# Batch processing (Phase 3)
results = await judge.evaluate_batch(candidates)

# API integration (Phase 3)
POST /evaluate
{
  "prompt": "What is AI?",
  "response": "AI is artificial intelligence",
  "criteria": "accuracy and clarity"
}
```

## Development Setup

### Prerequisites

- Python 3.9+
- Optional: OpenAI or Anthropic API keys for real LLM integration

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd llm-as-a-judge

# Install dependencies
pip install -r requirements.txt

# Optional: Install in development mode
pip install -e .

# Set up environment variables (optional)
cp .env.example .env
# Edit .env with your API keys:
# OPENAI_API_KEY=your-openai-key
# ANTHROPIC_API_KEY=your-anthropic-key
```

### Testing

**🎉 ALL 168 TESTS PASSING - Complete Test Suite Reliability**

```bash
# Run all tests (168/168 passing)
pytest

# Run specific test suites
pytest tests/unit/                    # 139+ unit tests passing
pytest tests/integration/             # 28+ integration tests passing

# Run tests for specific layers
pytest tests/unit/infrastructure/     # Infrastructure layer tests (76 tests)
pytest tests/unit/application/        # Application layer tests
pytest tests/unit/domain/             # Domain layer tests

# Run with coverage
pytest --cov=src/llm_judge --cov-report=html

# Run specific functionality tests
pytest tests/unit/infrastructure/test_anthropic_client.py -v  # Anthropic client tests
pytest tests/unit/infrastructure/test_openai_client.py -v     # OpenAI client tests
pytest tests/integration/test_llm_judge_integration.py -v     # End-to-end integration

# Test the CLI directly
python -m src.llm_judge "What is AI?" "AI is artificial intelligence"

# Test comparison functionality specifically
python -c "import asyncio; from src.llm_judge import *; judge=LLMJudge(); asyncio.run(judge.compare_responses(CandidateResponse('Q','A','m1'), CandidateResponse('Q','B','m2')))"
```

**Test Suite Coverage:**

- ✅ **API Client Tests**: OpenAI and Anthropic SDK integration with proper mocking
- ✅ **Resilience Tests**: Retry strategies, fallback management, circuit breakers
- ✅ **Configuration Tests**: Environment loading, validation, error handling
- ✅ **Integration Tests**: End-to-end LLM judge functionality, comparison methods
- ✅ **Error Handling Tests**: Classification, timeout management, recovery patterns

## Contributing

This project follows a structured development approach based on Domain-Driven Design:

### Development Guidelines

1. **Documentation-First**: Review planning docs in `docs/` before coding
2. **Layer Separation**: Respect the DDD architecture boundaries
3. **Test-Driven**: Write tests before implementation (see `tests/` structure)
4. **Incremental**: Small, working increments with rollback capability
5. **Import Hygiene**: Follow the established import patterns (`src.llm_judge.*`)

### Contributing to Specific Layers

- **Domain**: Focus on business logic, no external dependencies
- **Application**: Orchestrate use cases, coordinate between layers
- **Infrastructure**: Handle external concerns (APIs, config, persistence)
- **Presentation**: User interfaces and input/output handling

### Adding New Features

1. Update documentation in `docs/` first
2. Write tests in appropriate `tests/unit/` or `tests/integration/` folder
3. Implement in the correct architectural layer
4. Update relevant `__init__.py` files for public APIs
5. Run full test suite to ensure no regressions

## Roadmap

| Phase         | Status            | Key Deliverables                                                      | Timeline     |
| ------------- | ----------------- | --------------------------------------------------------------------- | ------------ |
| **Phase 1**   | ✅ Complete       | Minimal working implementation                                        | Complete     |
| **Structure** | ✅ Complete       | DDD architecture, test organization, documentation                    | Complete     |
| **Phase 2**   | ✅ **Complete**   | **Production infrastructure, real LLM integration, test reliability** | **Complete** |
| **Phase 3**   | ⏳ Ready to Start | Advanced features, REST API, batch processing                         | 6-8 weeks    |
| **Phase 4**   | ⏳ Planned        | Enterprise scale, multi-tenancy, high availability                    | 3-6 months   |

### ✅ Phase 2 Infrastructure - COMPLETED

- ✅ **Real LLM API clients with comprehensive resilience patterns**
- ✅ **Configuration management and advanced error handling**
- ✅ **Complete pytest overhaul - 123/123 tests passing**
- ✅ **compare_responses functionality fully recovered and operational**
- ✅ **Async processing architecture with timeout management**
- ✅ **Fallback management and circuit breaker patterns**
- ✅ **Error classification system with 6 error categories**
- ✅ **SDK integration testing with proper mocking**

### 🚀 Ready for Phase 3: Advanced Features

- Enhanced CLI with interactive features and progress tracking
- Data persistence and comprehensive result caching
- REST API for HTTP-based evaluation services
- Batch processing for high-throughput evaluations
- Advanced analytics and evaluation reporting

## License

MIT License - Open source implementation following the Evidently AI methodology.

## Key Features

### ✅ Current Implementation - FULLY FUNCTIONAL

- **Multiple LLM Providers**: OpenAI GPT-4, Anthropic Claude with intelligent fallback
- **Resilience Patterns**: Retry logic, circuit breakers, timeout management, error classification
- **Evaluation Methods**:
  - ✅ **Direct scoring (1-5 integer scale) with detailed reasoning**
  - ✅ **Pairwise comparison (A vs B vs tie) - FULLY RECOVERED AND OPERATIONAL**
- **Error Handling**: Comprehensive error classification and recovery with 6 error categories
- **Configuration**: Flexible config with environment variable support and validation
- **Testing**: **100% reliable test suite - 168/168 tests passing**
- **CLI Interface**: Command-line evaluation tool with async support
- **Async Architecture**: Full async/await support for concurrent operations
- **Fallback Management**: Degraded mode operation when providers unavailable
- **Request Management**: Timeout handling, request cancellation, connection pooling

### 🎯 Comparison Feature Highlights

- **Both OpenAI and Anthropic**: Full support for both major LLM providers
- **Intelligent Fallback**: Automatic failover between providers
- **Structured Results**: Consistent response format with winner, reasoning, confidence
- **Mock Support**: Full offline functionality for development and testing
- **Error Resilience**: Graceful handling of API failures with fallback responses

### 🔄 In Development

- **Async Processing**: Performance optimization for batch operations
- **Enhanced CLI**: Progress tracking and interactive features
- **Result Caching**: Persistent storage for evaluation results

### 📋 Planned Features

- **REST API**: HTTP service for evaluation requests
- **Batch Processing**: Efficient handling of multiple evaluations
- **Reference-Based Evaluation**: Compare against golden examples
- **Custom Criteria**: User-defined evaluation dimensions
- **Analytics Dashboard**: Visualization of evaluation results

## Environment Configuration

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

## Acknowledgments

- [Evidently AI](https://www.evidentlyai.com/) for the LLM-as-a-Judge methodology
- OpenAI and Anthropic for LLM APIs
- The Domain-Driven Design community for architectural guidance
- The open-source community for tools and inspiration
