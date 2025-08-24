# LLM-as-a-Judge System

A minimal implementation of an LLM-as-a-Judge system for evaluating language model outputs, based on the [Evidently AI guide](https://www.evidentlyai.com/llm-guide/llm-as-a-judge).

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment (optional - for real LLM integration)
cp .env.example .env
# Edit .env with your API keys

# Run as module
python -m src.llm_judge "What is AI?" "AI is artificial intelligence"

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
│   │   ├── evaluation/              # Core evaluation domain logic
│   │   └── models/                  # Domain models and value objects
│   ├── application/                 # Use cases and application services
│   │   ├── services/                # Application services
│   │   │   └── llm_judge_service.py # Main LLM judge implementation
│   │   └── use_cases/               # Specific use case implementations
│   ├── infrastructure/              # External concerns and technical details
│   │   ├── clients/                 # LLM provider API clients
│   │   │   ├── openai_client.py     # OpenAI API integration
│   │   │   ├── anthropic_client.py  # Anthropic API integration
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
├── tests/                           # Test suite organized by layer
│   ├── unit/                        # Unit tests (isolated, fast)
│   │   ├── domain/                  # Domain layer tests
│   │   ├── application/             # Application layer tests
│   │   └── infrastructure/          # Infrastructure layer tests
│   │       ├── test_*_client.py     # API client tests
│   │       ├── test_config.py       # Configuration tests
│   │       └── test_*_manager.py    # Resilience component tests
│   └── integration/                 # Integration tests (cross-layer)
│       ├── test_llm_judge_integration.py # End-to-end judge tests
│       ├── test_error_integration.py     # Error handling integration
│       └── test_timeout_integration.py   # Timeout behavior tests
├── docs/                            # Layered documentation strategy
│   ├── README.md                    # Documentation navigation guide
│   ├── STRATEGY.md                  # Business vision and objectives
│   ├── ARCHITECTURE.md              # System design and patterns
│   ├── DOMAIN-MODEL.md              # Business concepts and language
│   ├── IMPLEMENTATION.md            # Technical execution details
│   └── TASKS.md                     # Current iteration breakdown
├── logs/                            # Application logs (gitignored)
├── .env.example                     # Environment variables template
├── .gitignore                       # Git ignore patterns
├── pytest.ini                      # Pytest configuration
├── requirements.txt                 # Python dependencies
└── README.md                        # This file - project overview
```

## Current Status

✅ **Project Structure Reorganization Complete**
- ✅ Domain-Driven Design (DDD) layered architecture implemented
- ✅ Clean separation of concerns across domain, application, infrastructure, and presentation layers
- ✅ Comprehensive test suite organization by layer and type (unit/integration)
- ✅ Updated import paths and package structure throughout codebase
- ✅ CLI entry point available via `python -m src.llm_judge`
- ✅ All existing functionality preserved and verified working

✅ **Phase 1 Complete**: Working Minimal Implementation
- ✅ Direct scoring evaluation (1-5 scale) with structured reasoning
- ✅ Pairwise comparison (A vs B vs tie) with dimensional analysis  
- ✅ Mock LLM integration for development and testing
- ✅ Command-line demo interface with examples
- ✅ Comprehensive planning documentation across all architectural levels

🟡 **Phase 2 Infrastructure**: Production-Ready Foundation
- ✅ Real LLM API integration (OpenAI GPT-4, Anthropic Claude)
- ✅ Robust error handling and retry logic with circuit breakers
- ✅ Configuration management with hierarchical loading
- ✅ Timeout management and request cancellation
- ✅ Fallback mechanisms and degraded service modes
- ⏳ Async processing architecture optimization
- ⏳ Enhanced CLI interface with progress tracking
- ⏳ Data persistence and caching layer

## Implementation Documentation

### 📋 Layered Documentation Strategy

Following the AI Coding Agent Governance Framework, we maintain sophisticated documentation across multiple abstraction levels:

| Document | Abstraction Level | Purpose | Primary Audience |
|----------|-------------------|---------|------------------|
| [docs/STRATEGY.md](docs/STRATEGY.md) | **Strategic** | Business vision, market analysis, success metrics | C-Suite, Product Strategy, Investors |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | **Architectural** | System design, component relationships, scalability | Solution Architects, Technical Leadership |
| [docs/DOMAIN-MODEL.md](docs/DOMAIN-MODEL.md) | **Domain** | Business concepts, ubiquitous language, domain rules | Domain Experts, Senior Developers |
| [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) | **Implementation** | Detailed technical execution with acceptance criteria | Development Teams, DevOps Engineers |
| [docs/TASKS.md](docs/TASKS.md) | **Task** | Current sprint breakdown with validation gates | Individual Developers, Scrum Masters |
| [CODE_PLAN.md](CODE_PLAN.md) | **Code** | Specific code structure and implementation examples | Junior/Mid-level Developers |

### 🎯 Documentation Synchronization Status

| Document | Last Updated | Sync Status | Code Alignment |
|----------|-------------|-------------|----------------|
| STRATEGY.md | Current | ✅ Synchronized | Reflects current business objectives |
| ARCHITECTURE.md | Current | ✅ Synchronized | Matches planned system design |
| DOMAIN-MODEL.md | Current | ✅ Synchronized | Captures current domain understanding |
| IMPLEMENTATION.md | Current | ✅ Synchronized | Detailed Phase 1 completion, Phase 2 planning |
| TASKS.md | Current | ✅ Synchronized | Active sprint tasks with validation gates |
| CODE_PLAN.md | Current | ✅ Synchronized | Matches current code structure |
| README.md | Current | ✅ Synchronized | Reflects actual system state and capabilities |

### 🎯 Development Phases

#### Phase 1: MVP ✅ COMPLETE
- ✅ Single-file working implementation
- ✅ Core evaluation methods
- ✅ Demo functionality

#### Phase 2: Production Foundation (Next)
- [ ] Real LLM API integration (OpenAI, Anthropic)
- [ ] Error handling and retry logic
- [ ] Configuration management
- [ ] Data persistence
- [ ] Enhanced CLI interface

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
- **Direct Scoring**: Rate responses on 1-5 scale with reasoning
- **Pairwise Comparison**: Compare two responses (A vs B vs tie)
- **Reference-Based**: Compare against golden examples *(planned)*

### LLM Provider Support
- **Current**: Mock integration for testing
- **Planned**: OpenAI GPT-4, Anthropic Claude, Local models

### Evaluation Criteria
- **Current**: Single criteria (e.g., "overall quality")
- **Planned**: Multi-dimensional evaluation, custom criteria

## Usage Examples

### Current Usage
```python
# Import from the organized package structure
from src.llm_judge import LLMJudge, CandidateResponse, LLMConfig

# Basic usage with default configuration
judge = LLMJudge()

# Single evaluation
candidate = CandidateResponse(
    prompt="What is AI?",
    response="AI is artificial intelligence",
    model="gpt-3.5"
)

result = judge.evaluate_response(candidate, "accuracy and clarity")
print(f"Score: {result.score}/5")
print(f"Reasoning: {result.reasoning}")

# Using custom configuration
config = LLMConfig(
    openai_api_key="your-api-key",
    default_provider="openai",
    openai_model="gpt-4"
)
judge = LLMJudge(config=config)

# CLI usage
# python -m src.llm_judge "What is AI?" "AI is artificial intelligence"
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
```bash
# Run all tests
pytest

# Run specific test suites
pytest tests/unit/                    # Unit tests only
pytest tests/integration/             # Integration tests only

# Run tests for specific layers
pytest tests/unit/infrastructure/     # Infrastructure layer tests
pytest tests/unit/application/        # Application layer tests
pytest tests/unit/domain/             # Domain layer tests

# Run with coverage
pytest --cov=src/llm_judge --cov-report=html

# Run specific test file
pytest tests/unit/infrastructure/test_config.py -v

# Test the CLI directly
python -m src.llm_judge "What is AI?" "AI is artificial intelligence"
```

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

| Phase | Status | Key Deliverables | Timeline |
|-------|--------|------------------|----------|
| **Phase 1** | ✅ Complete | Minimal working implementation | Complete |
| **Structure** | ✅ Complete | DDD architecture, test organization, documentation | Complete |
| **Phase 2** | 🟡 In Progress | Production infrastructure, real LLM integration | 2-4 weeks |
| **Phase 3** | ⏳ Planned | Advanced features, REST API, batch processing | 6-8 weeks |
| **Phase 4** | ⏳ Planned | Enterprise scale, multi-tenancy, high availability | 3-6 months |

### Current Focus: Phase 2 Infrastructure
- ✅ Real LLM API clients with resilience patterns
- ✅ Configuration management and error handling
- ⏳ Async processing and performance optimization
- ⏳ Enhanced CLI with progress tracking
- ⏳ Data persistence and result caching

## License

MIT License - Open source implementation following the Evidently AI methodology.

## Key Features

### ✅ Current Implementation
- **Multiple LLM Providers**: OpenAI GPT-4, Anthropic Claude with fallback
- **Resilience Patterns**: Retry logic, circuit breakers, timeout management
- **Evaluation Methods**: Direct scoring (1-5 scale), pairwise comparison
- **Error Handling**: Comprehensive error classification and recovery
- **Configuration**: Flexible config with environment variable support
- **Testing**: Full test suite with unit and integration tests
- **CLI Interface**: Simple command-line evaluation tool

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