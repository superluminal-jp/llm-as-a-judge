# API Reference

This section provides comprehensive API documentation for the LLM-as-a-Judge system.

## 📖 API Documentation

### Core Classes

- **[LLMJudge](reference.md#llmjudge)** - Main evaluation class
- **[CandidateResponse](reference.md#candidateresponse)** - Response to evaluate
- **[MultiCriteriaResult](reference.md#multicriteriaresult)** - Evaluation results
- **[EvaluationCriteria](reference.md#evaluationcriteria)** - Custom criteria

### Usage Patterns

- **[Basic Evaluation](examples.md#basic-evaluation)** - Single response evaluation
- **[Response Comparison](examples.md#response-comparison)** - Compare two responses
- **[Batch Processing](examples.md#batch-processing)** - Process multiple evaluations
- **[Custom Criteria](examples.md#custom-criteria)** - Define custom evaluation criteria

### Configuration

- **[LLMConfig](reference.md#llmconfig)** - System configuration
- **[Environment Setup](examples.md#environment-setup)** - Configuration examples
- **[Provider Selection](examples.md#provider-selection)** - LLM provider configuration

## 🚀 Quick Start

### Basic Usage

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

    result = await judge.evaluate_multi_criteria(candidate)
    print(f"Overall Score: {result.aggregated.overall_score:.1f}/5")

    await judge.close()

asyncio.run(basic_evaluation())
```

### Response Comparison

```python
async def compare_responses():
    judge = LLMJudge()

    candidate_a = CandidateResponse("Q", "Response A", "model-a")
    candidate_b = CandidateResponse("Q", "Response B", "model-b")

    result = await judge.compare_responses(candidate_a, candidate_b)
    print(f"Winner: {result['winner']}")

    await judge.close()

asyncio.run(compare_responses())
```

## 📚 Documentation

- **[Complete API Reference](reference.md)** - Detailed API documentation
- **[Code Examples](examples.md)** - Practical usage examples
- **[Configuration Guide](../configuration/README.md)** - System configuration
- **[Getting Started](../getting-started/README.md)** - Quick start guide

## 🆘 Need Help?

- Check the [FAQ](../overview/README.md#faq)
- Review [Common Issues](../overview/README.md#common-issues)
- [Open an issue](https://github.com/superluminal-jp/llm-as-a-judge/issues)
