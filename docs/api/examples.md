# API Examples

This document provides practical examples of using the LLM-as-a-Judge API.

## Basic Evaluation

### Single Response Evaluation

```python
from src.llm_judge import LLMJudge, CandidateResponse
import asyncio

async def basic_evaluation():
    judge = LLMJudge()

    candidate = CandidateResponse(
        prompt="What is machine learning?",
        response="Machine learning is a subset of AI that enables computers to learn from data",
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

### Single-Criterion Evaluation

```python
async def single_criterion_evaluation():
    judge = LLMJudge()

    candidate = CandidateResponse(
        prompt="Explain quantum computing",
        response="Quantum computing uses quantum bits in superposition",
        model="gpt-4"
    )

    # Single-criterion evaluation
    result = await judge.evaluate_response(
        candidate,
        "accuracy and completeness",
        use_multi_criteria=False
    )

    print(f"Score: {result.score}/5")
    print(f"Reasoning: {result.reasoning}")

    await judge.close()

asyncio.run(single_criterion_evaluation())
```

## Response Comparison

### Basic Comparison

```python
async def compare_responses():
    judge = LLMJudge()

    candidate_a = CandidateResponse(
        prompt="Explain machine learning",
        response="ML is a subset of AI",
        model="gpt-3.5"
    )

    candidate_b = CandidateResponse(
        prompt="Explain machine learning",
        response="Machine learning is a subset of artificial intelligence that enables computers to learn from data without being explicitly programmed",
        model="gpt-4"
    )

    result = await judge.compare_responses(candidate_a, candidate_b)

    print(f"Winner: {result['winner']}")  # 'A', 'B', or 'tie'
    print(f"Reasoning: {result['reasoning']}")
    print(f"Confidence: {result['confidence']}")

    await judge.close()

asyncio.run(compare_responses())
```

## Custom Criteria

### Using Criteria Files

```python
from src.llm_judge.domain.evaluation.criteria import EvaluationCriteria

async def load_criteria_from_file():
    judge = LLMJudge()

    # Load criteria from JSON file
    criteria = EvaluationCriteria.from_file("criteria/default.json")

    candidate = CandidateResponse(
        prompt="What is machine learning?",
        response="Machine learning is a subset of AI that enables computers to learn from data",
        model="gpt-4"
    )

    result = await judge.evaluate_multi_criteria(candidate, criteria=criteria)

    print(f"Score: {result.aggregated.overall_score:.1f}/5")
    for cs in result.criterion_scores:
        print(f"{cs.criterion_name}: {cs.score}/5")

    await judge.close()

asyncio.run(load_criteria_from_file())
```

### Define Custom Criteria

```python
from src.llm_judge.domain.evaluation.criteria import (
    EvaluationCriteria, CriterionDefinition, CriterionType
)

async def custom_criteria_evaluation():
    judge = LLMJudge()

    # Define custom criteria for code review
    code_review_criteria = EvaluationCriteria(
        name="code_review",
        description="Code review evaluation criteria",
        criteria=[
            CriterionDefinition(
                name="correctness",
                description="Code correctness and functionality",
                criterion_type=CriterionType.FACTUAL,
                weight=0.4
            ),
            CriterionDefinition(
                name="readability",
                description="Code readability and style",
                criterion_type=CriterionType.QUALITATIVE,
                weight=0.3
            ),
            CriterionDefinition(
                name="efficiency",
                description="Performance and efficiency",
                criterion_type=CriterionType.STRUCTURAL,
                weight=0.3
            )
        ]
    )

    candidate = CandidateResponse(
        prompt="Write a function to sort a list",
        response="def sort_list(lst): return sorted(lst)",
        model="code-assistant"
    )

    result = await judge.evaluate_multi_criteria(candidate, criteria=code_review_criteria)

    print(f"Code Review Score: {result.aggregated.overall_score:.1f}/5")
    for cs in result.criterion_scores:
        print(f"{cs.criterion_name}: {cs.score}/5 (weight: {cs.weight:.1%})")

    await judge.close()

asyncio.run(custom_criteria_evaluation())
```

## Batch Processing

### Process Multiple Evaluations

```python
from src.llm_judge import BatchProcessingService, LLMJudge

async def batch_processing():
    judge = LLMJudge()
    batch_service = BatchProcessingService(judge, max_workers=5)

    # Progress tracking
    def progress_callback(progress):
        completed = progress.completed_items + progress.failed_items
        percentage = (completed / progress.total_items) * 100
        print(f"Progress: {percentage:.1f}% ({completed}/{progress.total_items})")

    result = await batch_service.process_batch_from_file(
        "evaluations.jsonl",
        output_path="results.json",
        batch_config={
            "max_concurrent_items": 8,
            "retry_failed_items": True,
            "max_retries_per_item": 2
        },
        progress_callback=progress_callback
    )

    print(f"Success rate: {result.success_rate:.1%}")
    print(f"Total time: {result.processing_duration:.1f}s")

    await judge.close()

asyncio.run(batch_processing())
```

## Configuration

### Environment Setup

```python
from src.llm_judge.infrastructure.config.config import LLMConfig

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

### Provider Selection

```python
# Use specific provider
config = LLMConfig(
    default_provider="openai",
    openai_api_key="sk-your-key"
)

judge = LLMJudge(config=config)

# Or specify at runtime
result = await judge.evaluate_multi_criteria(
    candidate,
    judge_model="gpt-4"
)
```

## Error Handling

### Comprehensive Error Handling

```python
import logging
from src.llm_judge.infrastructure.resilience.error_classification import ErrorType

async def robust_evaluation():
    judge = LLMJudge()

    try:
        result = await judge.evaluate_multi_criteria(candidate)
        print(f"Evaluation successful: {result.aggregated.overall_score}")

    except Exception as e:
        error_type = classify_error(e)

        if error_type == ErrorType.TRANSIENT:
            print("Transient error - will retry automatically")
        elif error_type == ErrorType.AUTHENTICATION:
            print("Authentication error - check API keys")
        elif error_type == ErrorType.RATE_LIMIT:
            print("Rate limit exceeded - will backoff and retry")
        else:
            print(f"Unexpected error: {e}")

    finally:
        await judge.close()

asyncio.run(robust_evaluation())
```

## Advanced Usage

### Custom Evaluation Criteria

```python
from src.llm_judge.domain.evaluation.custom_criteria import CustomCriteriaBuilder

# Build custom criteria programmatically
custom_criteria = (CustomCriteriaBuilder()
    .add_accuracy(weight=0.4)
    .add_clarity(weight=0.3)
    .add_relevance(weight=0.3)
    .build("custom_evaluation", "Custom 3-criteria evaluation"))

result = await judge.evaluate_multi_criteria(candidate, criteria=custom_criteria)
```

### Result Analysis

```python
async def analyze_results():
    judge = LLMJudge()

    result = await judge.evaluate_multi_criteria(candidate)

    # Get summary statistics
    summary = result.get_summary()
    print(f"Overall Score: {summary['overall_score']}")
    print(f"Confidence: {summary['confidence']}")

    # Get scores by type
    factual_scores = result.get_scores_by_type(CriterionType.FACTUAL)
    qualitative_scores = result.get_scores_by_type(CriterionType.QUALITATIVE)

    print(f"Factual scores: {[s.score for s in factual_scores]}")
    print(f"Qualitative scores: {[s.score for s in qualitative_scores]}")

    # Convert to legacy format
    legacy_result = result.to_legacy_format()
    print(f"Legacy format: {legacy_result}")

    await judge.close()

asyncio.run(analyze_results())
```

## Integration Examples

### Flask Web Application

```python
from flask import Flask, request, jsonify
from src.llm_judge import LLMJudge, CandidateResponse

app = Flask(__name__)
judge = LLMJudge()

@app.route('/evaluate', methods=['POST'])
async def evaluate_endpoint():
    data = request.json

    candidate = CandidateResponse(
        prompt=data['prompt'],
        response=data['response'],
        model=data.get('model', 'unknown')
    )

    result = await judge.evaluate_multi_criteria(candidate)

    return jsonify({
        'overall_score': result.aggregated.overall_score,
        'confidence': result.aggregated.confidence,
        'criterion_scores': [
            {
                'criterion': cs.criterion_name,
                'score': cs.score,
                'reasoning': cs.reasoning
            }
            for cs in result.criterion_scores
        ]
    })

if __name__ == '__main__':
    app.run(debug=True)
```

### FastAPI Application

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.llm_judge import LLMJudge, CandidateResponse

app = FastAPI()
judge = LLMJudge()

class EvaluationRequest(BaseModel):
    prompt: str
    response: str
    model: str = "unknown"

@app.post("/evaluate")
async def evaluate(request: EvaluationRequest):
    candidate = CandidateResponse(
        prompt=request.prompt,
        response=request.response,
        model=request.model
    )

    try:
        result = await judge.evaluate_multi_criteria(candidate)
        return {
            'overall_score': result.aggregated.overall_score,
            'confidence': result.aggregated.confidence,
            'criterion_scores': result.criterion_scores
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## Next Steps

- **[Complete API Reference](reference.md)** - Detailed API documentation
- **[Configuration Guide](../configuration/README.md)** - System configuration
- **[Architecture Overview](../architecture/README.md)** - System design
- **[Getting Started](../getting-started/README.md)** - Quick start guide
