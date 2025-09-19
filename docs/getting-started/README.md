# Getting Started

Welcome to the LLM-as-a-Judge system! This guide will help you get up and running quickly.

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd llm-as-a-judge

# Install dependencies
pip install -r requirements.txt

# Optional: Install in development mode
pip install -e .
```

### 2. Basic Setup

```bash
# Set up environment (optional - for real LLM integration)
cp .env.example .env
# Edit .env with your API keys
```

### 3. Your First Evaluation

```bash
# Multi-criteria evaluation (default)
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence"

# Compare two responses
python -m src.llm_judge compare "Explain ML" "Basic explanation" "Detailed explanation"
```

## 📚 Next Steps

- **[Installation Guide](installation.md)** - Detailed installation instructions
- **[First Steps](first-steps.md)** - Your first evaluation walkthrough
- **[Configuration](configuration/README.md)** - System configuration
- **[API Reference](api/README.md)** - Complete API documentation

## 🆘 Need Help?

- Check the [FAQ](../overview/README.md#faq)
- Review [Common Issues](../overview/README.md#common-issues)
- [Open an issue](https://github.com/superluminal-jp/llm-as-a-judge/issues)
