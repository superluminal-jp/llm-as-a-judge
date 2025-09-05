# Multi-Criteria Evaluation Guide

## Overview

The LLM-as-a-Judge system provides comprehensive multi-criteria evaluation by default, analyzing responses across 7 key dimensions to provide detailed, actionable feedback. This guide explains how to use and customize the multi-criteria evaluation system.

## Default Evaluation Criteria

### 7-Dimension Analysis

The system evaluates responses across these 7 criteria by default:

| Criterion | Weight | Scale | Description |
|-----------|--------|-------|-------------|
| **Accuracy** | 20% | 1-5 | Factual correctness and truthfulness of information |
| **Completeness** | 15% | 1-5 | Depth and comprehensiveness of coverage |
| **Clarity** | 15% | 1-5 | Clarity of expression and ease of understanding |
| **Relevance** | 15% | 1-5 | Direct relevance to the question asked |
| **Helpfulness** | 15% | 1-5 | Practical value and usefulness to the reader |
| **Coherence** | 10% | 1-5 | Logical flow and internal consistency |
| **Appropriateness** | 10% | 1-5 | Tone, style, and contextual appropriateness |

### Scoring System

- **Scale**: Each criterion is scored from 1-5
- **Weighting**: Scores are weighted based on importance (accuracy gets 20%, coherence gets 10%)
- **Aggregation**: Final score is calculated as weighted average across all criteria
- **Confidence**: Each criterion score includes a confidence level (0-100%)

## Using Multi-Criteria Evaluation

### CLI Usage

```bash
# Default multi-criteria evaluation
python -m llm_judge evaluate "What is AI?" "AI is artificial intelligence"

# Show detailed breakdown
python -m llm_judge evaluate "What is AI?" "AI is artificial intelligence" --show-detailed

# JSON output with all criterion details
python -m llm_judge --output json evaluate "What is AI?" "AI is artificial intelligence"

# Batch processing (all items use multi-criteria)
python -m llm_judge batch evaluations.jsonl --output results.json
```

### Programmatic Usage

```python
from src.llm_judge import LLMJudge, CandidateResponse
import asyncio

async def evaluate_with_multi_criteria():
    judge = LLMJudge()
    
    candidate = CandidateResponse(
        prompt="Explain machine learning",
        response="Machine learning is a subset of AI that enables computers to learn from data",
        model="gpt-4"
    )
    
    # Multi-criteria evaluation
    result = await judge.evaluate_multi_criteria(candidate)
    
    # Overall results
    print(f"Overall Score: {result.aggregated.overall_score:.1f}/5")
    print(f"Confidence: {result.aggregated.confidence:.1%}")
    print(f"Criteria Count: {len(result.criterion_scores)}")
    
    # Individual criterion scores
    for cs in result.criterion_scores:
        print(f"{cs.criterion_name}: {cs.score}/5 (weight: {cs.weight:.1%})")
        print(f"  Reasoning: {cs.reasoning}")
        print(f"  Confidence: {cs.confidence:.1%}")
    
    # Qualitative feedback
    print(f"\\nOverall Assessment: {result.overall_reasoning}")
    print(f"Strengths: {', '.join(result.strengths)}")
    print(f"Areas for Improvement: {', '.join(result.weaknesses)}")
    print(f"Suggestions: {', '.join(result.suggestions)}")
    
    await judge.close()

asyncio.run(evaluate_with_multi_criteria())
```

## Output Formats

### Rich CLI Display

The default CLI output uses the Rich library to provide beautiful formatted results:

```
🎯 Multi-Criteria LLM Evaluation Results
================================================================================
╭─────────────────────────────── Overall Score ────────────────────────────────╮
│ 3.8/5.0                                                                      │
│ Confidence: 88.5%                                                            │
│ Based on 7 criteria                                                          │
╰──────────────────────────────────────────────────────────────────────────────╯

📊 Detailed Criterion Scores
┏━━━━━━━━━━━━┳━━━━┳━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Criterion  ┃ Sc…┃ We… ┃ Con… ┃ Reasoning                                     ┃
┡━━━━━━━━━━━━╇━━━━╇━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ accuracy   │ 4.0│ 20% │ 90%  │ Factually correct information                 │
│ clarity    │ 4.0│ 15% │ 85%  │ Clear and well-articulated                    │
│ relevance  │ 5.0│ 15% │ 95%  │ Directly addresses the question               │
│ coherence  │ 4.0│ 10% │ 85%  │ Logical flow and consistency                  │
│ complete…  │ 2.0│ 15% │ 90%  │ Lacks depth and comprehensive coverage        │
│ helpful…   │ 3.0│ 15% │ 80%  │ Provides basic understanding                  │
│ appropri…  │ 4.0│ 10% │ 80%  │ Appropriate tone and style                    │
└────────────┴────┴─────┴──────┴───────────────────────────────────────────────┘

📈 Score Statistics
    ┌────────────────────┬───────────┐
    │ Mean Score         │      3.57 │
    │ Median Score       │      4.00 │
    │ Score Range        │ 2.0 - 5.0 │
    │ Standard Deviation │      1.04 │
    └────────────────────┴───────────┘

💭 Overall Assessment
╭──────────────────────────────────────────────────────────────────────────────╮
│ The response provides accurate information but lacks comprehensive coverage.  │
│ While clear and relevant, it would benefit from more detailed explanation    │
│ and examples to improve helpfulness and completeness.                        │
╰──────────────────────────────────────────────────────────────────────────────╯

✅ Strengths
  • Factually accurate information
  • Clear and easy to understand
  • Directly relevant to the question

⚠️ Areas for Improvement
  • Lacks comprehensive coverage
  • Missing examples and applications
  • Could provide more practical context

💡 Suggestions
  • Add specific examples of machine learning applications
  • Explain key concepts like supervised vs unsupervised learning
  • Include information about how ML differs from traditional programming
```

### JSON Output

Comprehensive JSON output includes all criterion details:

```json
{
  "type": "multi_criteria_evaluation",
  "overall_score": 3.8,
  "overall_confidence": 0.885,
  "criteria_count": 7,
  "judge_model": "claude-sonnet-4-20250514",
  "evaluation_timestamp": "2025-09-06T00:23:15.631549",
  "weighted_score": 3.8,
  "mean_score": 3.57,
  "median_score": 4.0,
  "score_std": 1.04,
  "score_range": [2.0, 5.0],
  "criterion_scores": [
    {
      "criterion": "accuracy",
      "score": 4.0,
      "percentage": 75.0,
      "reasoning": "The response is factually correct. Machine learning is indeed a subset of AI...",
      "confidence": 0.9,
      "weight": 0.2
    },
    {
      "criterion": "completeness",
      "score": 2.0,
      "percentage": 25.0,
      "reasoning": "While accurate, the response lacks depth and comprehensive coverage...",
      "confidence": 0.9,
      "weight": 0.15
    }
  ],
  "overall_reasoning": "The response provides accurate information but lacks comprehensive coverage...",
  "strengths": [
    "Factually accurate information",
    "Clear and easy to understand",
    "Directly relevant to the question"
  ],
  "weaknesses": [
    "Lacks comprehensive coverage",
    "Missing examples and applications",
    "Could provide more practical context"
  ],
  "suggestions": [
    "Add specific examples of machine learning applications",
    "Explain key concepts like supervised vs unsupervised learning",
    "Include information about how ML differs from traditional programming"
  ]
}
```

## Customizing Evaluation Criteria

### Using Different Criteria Sets

```python
from src.llm_judge.domain.evaluation.criteria import DefaultCriteria

# Basic criteria (4 dimensions)
basic_criteria = DefaultCriteria.basic()

# Technical criteria (focused on technical accuracy)
technical_criteria = DefaultCriteria.technical()

# Creative criteria (includes creativity and originality)
creative_criteria = DefaultCriteria.creative()

# Use custom criteria
result = await judge.evaluate_multi_criteria(candidate, criteria=basic_criteria)
```

### Creating Custom Criteria

```python
from src.llm_judge.domain.evaluation.criteria import (
    EvaluationCriteria, 
    CriterionDefinition, 
    CriterionType
)

# Define custom criteria
custom_criteria = EvaluationCriteria(
    name="domain_specific_evaluation",
    description="Evaluation criteria for technical documentation",
    criteria=[
        CriterionDefinition(
            name="technical_accuracy",
            description="Correctness of technical information",
            criterion_type=CriterionType.FACTUAL,
            weight=0.4,
            scale_min=1,
            scale_max=5,
            examples={
                5: "All technical details are correct and verified",
                3: "Generally correct with minor technical issues",
                1: "Contains significant technical errors"
            }
        ),
        CriterionDefinition(
            name="code_quality",
            description="Quality and best practices in code examples",
            criterion_type=CriterionType.STRUCTURAL,
            weight=0.3,
            scale_min=1,
            scale_max=5
        ),
        CriterionDefinition(
            name="practical_usefulness",
            description="Practical value for developers",
            criterion_type=CriterionType.QUALITATIVE,
            weight=0.3,
            scale_min=1,
            scale_max=5
        )
    ]
)

# Use custom criteria
result = await judge.evaluate_multi_criteria(candidate, criteria=custom_criteria)
```

## Batch Processing with Multi-Criteria

### Batch File Format

Multi-criteria evaluation works seamlessly with batch processing:

```jsonl
{"type": "single", "prompt": "What is AI?", "response": "AI is artificial intelligence", "model": "gpt-4"}
{"type": "single", "prompt": "Explain ML", "response": "Machine learning enables computers to learn from data", "model": "claude-3"}
{"type": "comparison", "prompt": "Define cloud computing", "response_a": "Cloud is remote servers", "response_b": "Cloud computing provides on-demand access to computing resources", "model_a": "basic-model", "model_b": "advanced-model"}
```

### Batch Processing Commands

```bash
# Process batch with multi-criteria evaluation
python -m llm_judge batch evaluations.jsonl --output detailed_results.json

# High concurrency batch processing
python -m llm_judge batch large_dataset.jsonl --max-concurrent 20 --output results.json

# Batch with progress tracking
python -m llm_judge batch evaluations.jsonl --batch-name "Model Evaluation Study"
```

### Batch Results

Batch results include comprehensive multi-criteria data for each item:

```json
{
  "batch_summary": {
    "batch_id": "eval-2025-09-06",
    "total_items": 100,
    "successful_items": 98,
    "success_rate": 0.98,
    "processing_duration": 120.5,
    "average_processing_time": 1.23
  },
  "results": [
    {
      "item_id": "item-001",
      "status": "success",
      "evaluation_type": "single",
      "result": {
        "score": 4.1,
        "reasoning": "Comprehensive multi-criteria analysis...",
        "confidence": 0.91,
        "metadata": {
          "multi_criteria": true,
          "criteria_count": 7,
          "individual_scores": {
            "accuracy": {"score": 4.0, "reasoning": "Factually correct"},
            "clarity": {"score": 4.5, "reasoning": "Very clear explanation"}
          }
        }
      }
    }
  ]
}
```

## Backward Compatibility

### Single-Criterion Mode

For users who prefer the original single-criterion evaluation:

```bash
# CLI single-criterion mode
python -m llm_judge evaluate "What is AI?" "AI is artificial intelligence" --single-criterion --criteria "accuracy"

# Programmatic single-criterion
result = await judge.evaluate_response(candidate, "accuracy", use_multi_criteria=False)
```

### Migration from Legacy

Existing code continues to work but now gets enhanced multi-criteria results by default:

```python
# This now returns multi-criteria results in backward-compatible format
result = await judge.evaluate_response(candidate, "overall quality")
print(f"Score: {result.score}")  # Overall weighted score
print(f"Reasoning: {result.reasoning}")  # Comprehensive reasoning
print(f"Confidence: {result.confidence}")  # Aggregated confidence

# Access multi-criteria details through metadata
if hasattr(result, 'metadata') and result.metadata.get('multi_criteria'):
    individual_scores = result.metadata['individual_scores']
    for criterion, details in individual_scores.items():
        print(f"{criterion}: {details['score']}")
```

## Performance Considerations

### Processing Time

Multi-criteria evaluation takes longer than single-criterion due to comprehensive analysis:

- **Single-criterion**: ~2-5 seconds per evaluation
- **Multi-criteria**: ~15-25 seconds per evaluation
- **Batch processing**: Concurrent processing helps mitigate per-item cost

### Cost Optimization

For high-volume scenarios, consider:

1. **Selective multi-criteria**: Use multi-criteria for important evaluations, single-criterion for bulk processing
2. **Cached results**: The system includes result caching to avoid re-evaluation
3. **Batch processing**: Use concurrent evaluation to improve throughput
4. **Provider optimization**: Different LLM providers have different cost/performance characteristics

## Troubleshooting

### Common Issues

1. **JSON parsing errors**: The system includes robust JSON extraction with multiple fallback strategies
2. **Missing criteria**: System creates fallback scores for missing criteria
3. **Long processing times**: Use `--max-concurrent` to increase parallelism in batch processing
4. **API rate limits**: Built-in retry logic and backoff strategies handle rate limiting

### Debug Mode

```bash
# Enable verbose logging
python -m llm_judge --verbose evaluate "Question" "Answer"

# Check system status
python -m llm_judge --help
```

### Getting Help

- Check the main README.md for setup and configuration
- Review the CLI help: `python -m llm_judge --help`
- Examine batch result files for detailed error information
- Enable verbose mode for detailed logging

## Best Practices

### When to Use Multi-Criteria

- **High-stakes evaluations**: When you need comprehensive analysis
- **Model comparison**: Comparing different AI systems across multiple dimensions
- **Quality assessment**: Understanding specific strengths and weaknesses
- **Research applications**: When detailed metrics are needed

### When to Use Single-Criterion

- **High-volume processing**: When speed is more important than comprehensiveness
- **Specific focus**: When evaluating only one aspect (e.g., just factual accuracy)
- **Legacy compatibility**: When maintaining existing evaluation workflows

### Optimization Tips

1. **Use appropriate criteria**: Choose criteria sets that match your evaluation needs
2. **Leverage batch processing**: Process multiple items concurrently
3. **Monitor costs**: Track API usage and costs for budget management
4. **Cache results**: Avoid re-evaluating identical inputs
5. **Use JSON output**: For programmatic processing and analysis