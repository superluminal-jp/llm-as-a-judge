# Development Guide

This guide covers development practices and standards for the LLM-as-a-Judge system.

## Quick Start

### Development Setup

```bash
git clone <repository-url>
cd llm-as-a-judge
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pytest
```

## Development Principles

### Domain-Driven Design (DDD)

- **Domain Layer**: Core business logic
- **Application Layer**: Use cases and orchestration
- **Infrastructure Layer**: External concerns
- **Presentation Layer**: User interfaces

### Clean Code Standards

- **SOLID Principles**: Single responsibility, open/closed, etc.
- **Test-Driven Development**: Write tests first
- **Incremental Development**: Small, working increments
- **Documentation-First**: Update docs before coding

## Testing

### Running Tests

```bash
pytest                          # Run all tests
pytest tests/unit/              # Unit tests only
pytest --cov=src/llm_judge      # With coverage
```

## Development Workflow

1. **Create Feature Branch**
2. **Write Tests First**
3. **Implement Feature**
4. **Run Tests and Create PR**

## Coding Standards

- **PEP 8**: Python style guide
- **Type Hints**: For all functions
- **Docstrings**: Document public functions
- **Error Handling**: Comprehensive error handling

## Development Tools

```bash
black src/ tests/               # Format code
isort src/ tests/               # Sort imports
flake8 src/ tests/              # Check style
mypy src/                       # Type checking
```

## Getting Help

- **GitHub Issues**: Bug reports and feature requests
- **Documentation**: Comprehensive guides
- **Code Review**: Peer review and feedback

---

**Ready to contribute?** Check out the [Contributing Guidelines](contributing.md)!
