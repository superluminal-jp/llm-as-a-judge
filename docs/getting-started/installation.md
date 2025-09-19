# Installation Guide

This guide covers detailed installation instructions for the LLM-as-a-Judge system.

## Prerequisites

- Python 3.9 or higher
- pip (Python package installer)
- Git (for cloning the repository)

## Installation Methods

### Method 1: From Source (Recommended)

```bash
# Clone the repository
git clone https://github.com/superluminal-jp/llm-as-a-judge.git
cd llm-as-a-judge

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install in development mode
pip install -e .
```

### Method 2: Using pip (Future)

```bash
# When available on PyPI
pip install llm-as-a-judge
```

## Environment Setup

### 1. Create Environment File

```bash
# Copy the example environment file
cp .env.example .env
```

### 2. Configure API Keys

Edit the `.env` file with your API keys:

```bash
# LLM Provider API Keys
OPENAI_API_KEY=your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# Default Provider (openai or anthropic)
DEFAULT_PROVIDER=anthropic

# Model Configuration
OPENAI_MODEL=gpt-4
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

### 3. Verify Installation

```bash
# Test the installation
python -m src.llm_judge --help

# Run a simple evaluation
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence"
```

## Development Setup

For development work, install additional dependencies:

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks (optional)
pre-commit install

# Run tests to verify setup
pytest
```

## Troubleshooting

### Common Issues

1. **Python Version**: Ensure you're using Python 3.9+

   ```bash
   python --version
   ```

2. **Virtual Environment**: Always use a virtual environment

   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Dependencies**: If installation fails, try upgrading pip

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **API Keys**: Ensure your API keys are valid and have sufficient credits

### Getting Help

- Check the [FAQ](../overview/README.md#faq)
- Review [Common Issues](../overview/README.md#common-issues)
- [Open an issue](https://github.com/superluminal-jp/llm-as-a-judge/issues)

## Next Steps

- **[First Steps](first-steps.md)** - Your first evaluation walkthrough
- **[Configuration Guide](../configuration/README.md)** - System configuration
- **[API Reference](../api/README.md)** - Complete API documentation
