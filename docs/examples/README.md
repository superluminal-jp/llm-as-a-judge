# Examples and Tutorials

This section provides practical examples and tutorials for using the LLM-as-a-Judge system.

## 🚀 Quick Examples

### Basic Evaluation

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

## 📚 Example Categories

### Basic Usage

- **[Basic Evaluation](basic-usage.md)** - Simple evaluation examples
- **[Response Comparison](basic-usage.md#response-comparison)** - Compare two responses
- **[Custom Criteria](basic-usage.md#custom-criteria)** - Define custom evaluation criteria

### Advanced Usage

- **[Batch Processing](advanced-usage.md)** - Process multiple evaluations
- **[Custom Configuration](advanced-usage.md#custom-configuration)** - Advanced configuration options
- **[Error Handling](advanced-usage.md#error-handling)** - Robust error handling patterns

### Integration Examples

- **[Flask Integration](integration.md#flask)** - Web application integration
- **[FastAPI Integration](integration.md#fastapi)** - Modern API integration
- **[CLI Integration](integration.md#cli)** - Command-line integration

## 📁 Criteria File Examples

### Default Criteria

```json
{
  "name": "Default Evaluation Criteria",
  "description": "Comprehensive evaluation criteria for general use",
  "criteria": [
    {
      "name": "accuracy",
      "description": "Factual correctness and truthfulness",
      "weight": 0.25,
      "evaluation_prompt": "Rate the factual accuracy of this response",
      "examples": {
        "1": "Contains significant factual errors",
        "5": "Completely accurate and truthful"
      }
    },
    {
      "name": "completeness",
      "description": "Thoroughness and comprehensiveness",
      "weight": 0.2,
      "evaluation_prompt": "How complete is this response?",
      "examples": {
        "1": "Very incomplete, missing key information",
        "5": "Comprehensive and thorough"
      }
    }
  ]
}
```

### Custom Criteria

```json
{
  "name": "Technical Code Review",
  "description": "Criteria for evaluating technical code responses",
  "criteria": [
    {
      "name": "correctness",
      "description": "Code correctness and functionality",
      "weight": 0.4,
      "evaluation_prompt": "Is the code functionally correct?",
      "domain_specific": true,
      "metadata": {
        "category": "technical",
        "importance": "high"
      }
    },
    {
      "name": "readability",
      "description": "Code readability and style",
      "weight": 0.3,
      "evaluation_prompt": "How readable is the code?",
      "domain_specific": true
    },
    {
      "name": "efficiency",
      "description": "Performance and efficiency",
      "weight": 0.3,
      "evaluation_prompt": "How efficient is the code?",
      "domain_specific": true
    }
  ]
}
```

## 🎯 Use Case Examples

### Research and Development

- **Model Comparison**: Compare different LLM outputs
- **Prompt Engineering**: Optimize prompts for better responses
- **Quality Assurance**: Ensure consistent output quality

### Production Systems

- **Content Moderation**: Evaluate generated content
- **Response Quality**: Monitor AI assistant performance
- **A/B Testing**: Compare different response strategies

### Academic Research

- **Evaluation Studies**: Assess LLM capabilities
- **Benchmark Creation**: Develop evaluation datasets
- **Methodology Research**: Study evaluation techniques

## 🔧 Configuration Examples

### Environment Setup

```bash
# .env file
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
DEFAULT_PROVIDER=anthropic
```

### Criteria Configuration

```bash
# Use default criteria
python -m src.llm_judge evaluate "Question" "Answer" --criteria-file criteria/default.json

# Use custom criteria
python -m src.llm_judge evaluate "Question" "Answer" --criteria-file criteria/custom.json

# Use criteria template
python -m src.llm_judge evaluate "Question" "Answer" --criteria-file criteria/template.json
```

### Programmatic Configuration

```python
from src.llm_judge.infrastructure.config.config import LLMConfig
from src.llm_judge.domain.evaluation.criteria import EvaluationCriteria

# Load criteria from file
criteria = EvaluationCriteria.from_file("criteria/default.json")

config = LLMConfig(
    openai_api_key="sk-your-key",
    anthropic_api_key="sk-ant-your-key",
    default_provider="anthropic"
)

judge = LLMJudge(config=config)
```

## 📊 Output Examples

### Multi-Criteria Results

```python
result = await judge.evaluate_multi_criteria(candidate)

# Access overall score
print(f"Overall Score: {result.aggregated.overall_score:.1f}/5")

# Access individual criterion scores
for cs in result.criterion_scores:
    print(f"{cs.criterion_name}: {cs.score}/5 - {cs.reasoning}")

# Access strengths and weaknesses
print(f"Strengths: {result.strengths}")
print(f"Weaknesses: {result.weaknesses}")
print(f"Suggestions: {result.suggestions}")
```

### Comparison Results

```python
result = await judge.compare_responses(candidate_a, candidate_b)

print(f"Winner: {result['winner']}")  # 'A', 'B', or 'tie'
print(f"Reasoning: {result['reasoning']}")
print(f"Confidence: {result['confidence']}")
```

## 🧪 Testing Examples

### Unit Testing

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_evaluation():
    judge = LLMJudge()
    candidate = CandidateResponse("Q", "A", "model")

    result = await judge.evaluate_multi_criteria(candidate)

    assert result.aggregated.overall_score >= 1.0
    assert result.aggregated.overall_score <= 5.0
```

### Integration Testing

```python
@pytest.mark.integration
async def test_end_to_end():
    judge = LLMJudge()
    candidate = CandidateResponse("What is AI?", "AI is artificial intelligence", "gpt-4")

    result = await judge.evaluate_multi_criteria(candidate)

    assert result is not None
    assert len(result.criterion_scores) == 7
```

## 🚀 Performance Examples

### Batch Processing

```python
from src.llm_judge import BatchProcessingService

async def batch_example():
    judge = LLMJudge()
    batch_service = BatchProcessingService(judge, max_workers=5)

    result = await batch_service.process_batch_from_file(
        "evaluations.jsonl",
        output_path="results.json"
    )

    print(f"Success rate: {result.success_rate:.1%}")
```

### Concurrent Processing

```python
import asyncio

async def concurrent_evaluations():
    judge = LLMJudge()

    candidates = [
        CandidateResponse("Q1", "A1", "model1"),
        CandidateResponse("Q2", "A2", "model2"),
        CandidateResponse("Q3", "A3", "model3")
    ]

    tasks = [judge.evaluate_multi_criteria(c) for c in candidates]
    results = await asyncio.gather(*tasks)

    for i, result in enumerate(results):
        print(f"Candidate {i+1}: {result.aggregated.overall_score:.1f}/5")
```

## 📚 Related Documentation

- **[Basic Usage](basic-usage.md)** - Simple evaluation examples
- **[Advanced Usage](advanced-usage.md)** - Complex usage patterns
- **[Integration Examples](integration.md)** - System integration examples
- **[API Reference](../api/README.md)** - Complete API documentation

## 🆘 Need Help?

- Check the [FAQ](../overview/README.md#faq)
- Review [Common Issues](../overview/README.md#common-issues)
- [Open an issue](https://github.com/superluminal-jp/llm-as-a-judge/issues)

---

**Ready to try examples?** Start with [Basic Usage](basic-usage.md)!
