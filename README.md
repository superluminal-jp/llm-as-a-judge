# LLM-as-a-Judge System

A minimal implementation of an LLM-as-a-Judge system for evaluating language model outputs, based on the [Evidently AI guide](https://www.evidentlyai.com/llm-guide/llm-as-a-judge).

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run as module
python -m src.llm_judge "<prompt>" "<response>"

# Run tests
pytest
```

## Project Structure

The project follows Domain-Driven Design (DDD) principles with clean architecture:

```
llm-as-a-judge/
├── src/
│   └── llm_judge/
│       ├── domain/          # Business logic and domain models
│       ├── application/     # Use cases and application services
│       ├── infrastructure/  # External concerns (APIs, config, resilience)
│       └── presentation/    # User interfaces (CLI, etc.)
├── tests/
│   ├── unit/               # Unit tests by layer
│   └── integration/        # Integration tests
├── docs/                   # Layered documentation
└── logs/                   # Application logs (gitignored)
```

## Current Status

✅ **Phase 1 Complete**: Working Minimal Implementation (`llm_judge_simple.py`)
- ✅ Direct scoring evaluation (1-5 scale) with structured reasoning
- ✅ Pairwise comparison (A vs B vs tie) with dimensional analysis
- ✅ Mock LLM integration for development and testing
- ✅ Command-line demo interface with examples
- ✅ Comprehensive planning documentation across all architectural levels

🟡 **Phase 2 In Progress**: Production-Ready Foundation
- 🟡 Real LLM API integration (OpenAI GPT-4, Anthropic Claude)
- ⏳ Robust error handling and retry logic with circuit breakers
- ⏳ Configuration management with hierarchical loading
- ⏳ Async processing architecture for performance
- ⏳ Professional CLI interface with progress tracking

## Implementation Documentation

### 📋 Layered Planning Strategy

Following the AI Coding Agent Governance Framework, we maintain sophisticated documentation across multiple abstraction levels:

| Document | Abstraction Level | Purpose | Primary Audience |
|----------|-------------------|---------|------------------|
| [STRATEGY.md](STRATEGY.md) | **Strategic** | Business vision, market analysis, success metrics | C-Suite, Product Strategy, Investors |
| [ARCHITECTURE.md](ARCHITECTURE.md) | **Architectural** | System design, component relationships, scalability | Solution Architects, Technical Leadership |
| [DOMAIN-MODEL.md](DOMAIN-MODEL.md) | **Domain** | Business concepts, ubiquitous language, domain rules | Domain Experts, Senior Developers |
| [IMPLEMENTATION.md](IMPLEMENTATION.md) | **Implementation** | Detailed technical execution with acceptance criteria | Development Teams, DevOps Engineers |
| [TASKS.md](TASKS.md) | **Task** | Current sprint breakdown with validation gates | Individual Developers, Scrum Masters |
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

```
Current: Single File (100 LOC)
└── llm_judge_simple.py

Target: Modular Architecture
├── llm_judge/
│   ├── core/          # Domain models and logic
│   ├── clients/       # LLM provider integrations
│   ├── storage/       # Data persistence
│   ├── api/           # REST API server
│   └── cli/           # Command-line interface
├── tests/             # Test suites
└── docs/              # Documentation
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

### Current Simple Usage
```python
from llm_judge_simple import LLMJudge, CandidateResponse

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
# Current minimal version
# No installation needed - single file

# Future modular version (Phase 2+)
pip install -e .
pip install -r requirements-dev.txt
```

### Testing
```bash
# Current
python llm_judge_simple.py

# Future
pytest tests/
```

## Contributing

This project follows a structured development approach:

1. **Start with documentation**: Review planning docs before coding
2. **Follow phases**: Complete Phase 1 before starting Phase 2
3. **Test-driven**: Write tests before implementation
4. **Incremental**: Small, working increments with rollback capability

## Roadmap

| Milestone | Timeline | Key Deliverables |
|-----------|----------|------------------|
| Phase 1 | ✅ Complete | Working minimal implementation |
| Phase 2 | 2-4 weeks | Production-ready core with real LLM integration |
| Phase 3 | 6-8 weeks | Advanced features and API |
| Phase 4 | 3-6 months | Enterprise-scale deployment |

## License

MIT License - Open source implementation following the Evidently AI methodology.

## Acknowledgments

- [Evidently AI](https://www.evidentlyai.com/) for the LLM-as-a-Judge methodology
- OpenAI and Anthropic for LLM APIs
- The open-source community for tools and inspiration