# Multi-Criteria Weight Configuration Examples

This document provides practical examples of how to use custom weight configurations for different evaluation scenarios.

## Basic Usage Examples

### 1. Equal Weights (Default Alternative)

```bash
# Give all criteria equal importance
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence" --equal-weights
```

### 2. Custom Weights via CLI

```bash
# Emphasize accuracy and clarity
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence" \
  --criteria-weights "accuracy:0.4,clarity:0.3,helpfulness:0.2,relevance:0.1"

# Focus on completeness and coherence
python -m src.llm_judge evaluate "Explain ML" "Machine learning is..." \
  --criteria-weights "completeness:0.5,coherence:0.3,clarity:0.2"
```

### 3. Configuration File

```bash
# Use custom weights from config file
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence" \
  --config examples/custom_weights_config.json
```

## Scenario-Based Examples

### Academic/Research Content

For academic papers, research summaries, or educational content:

```bash
# Emphasize accuracy and completeness
python -m src.llm_judge evaluate "Explain quantum computing" "Quantum computing uses..." \
  --criteria-weights "accuracy:0.4,completeness:0.3,clarity:0.2,relevance:0.1"
```

### Creative Writing

For stories, poems, or creative content:

```bash
# Use creative criteria with emphasis on creativity and engagement
python -m src.llm_judge evaluate "Write a story about AI" "Once upon a time..." \
  --criteria-type creative \
  --criteria-weights "creativity:0.4,engagement:0.3,coherence:0.2,style:0.1"
```

### Technical Documentation

For API docs, technical guides, or code explanations:

```bash
# Emphasize clarity and technical accuracy
python -m src.llm_judge evaluate "Document this API" "This API provides..." \
  --criteria-type technical \
  --criteria-weights "clarity:0.4,technical_accuracy:0.3,completeness:0.2,best_practices:0.1"
```

### Customer Support Responses

For help desk, FAQ, or customer service content:

```bash
# Emphasize helpfulness and clarity
python -m src.llm_judge evaluate "How do I reset my password?" "To reset your password..." \
  --criteria-weights "helpfulness:0.4,clarity:0.3,accuracy:0.2,appropriateness:0.1"
```

### Marketing Content

For advertisements, product descriptions, or promotional material:

```bash
# Emphasize engagement and appropriateness
python -m src.llm_judge evaluate "Describe our product" "Our revolutionary product..." \
  --criteria-weights "engagement:0.3,appropriateness:0.3,clarity:0.2,relevance:0.2"
```

## Configuration File Examples

### Academic Evaluation Config

```json
{
  "default_provider": "openai",
  "default_criteria_type": "comprehensive",
  "criteria_weights": "accuracy:0.4,completeness:0.3,clarity:0.2,relevance:0.1",
  "use_equal_weights": false,
  "openai_model": "gpt-4",
  "log_level": "INFO"
}
```

### Creative Writing Config

```json
{
  "default_provider": "anthropic",
  "default_criteria_type": "creative",
  "criteria_weights": "creativity:0.4,engagement:0.3,coherence:0.2,style:0.1",
  "use_equal_weights": false,
  "anthropic_model": "claude-3-sonnet-20240229",
  "log_level": "INFO"
}
```

### Technical Documentation Config

```json
{
  "default_provider": "openai",
  "default_criteria_type": "technical",
  "criteria_weights": "clarity:0.4,technical_accuracy:0.3,completeness:0.2,best_practices:0.1",
  "use_equal_weights": false,
  "openai_model": "gpt-4",
  "log_level": "INFO"
}
```

### Equal Weights Config

```json
{
  "default_provider": "openai",
  "default_criteria_type": "comprehensive",
  "use_equal_weights": true,
  "openai_model": "gpt-4",
  "log_level": "INFO"
}
```

## Programmatic Usage

### Python API Example

```python
from src.llm_judge import LLMJudge, CandidateResponse
from src.llm_judge.domain.evaluation.criteria import DefaultCriteria
from src.llm_judge.domain.evaluation.weight_config import WeightConfigParser, CriteriaWeightApplier
import asyncio

async def evaluate_with_custom_weights():
    judge = LLMJudge()

    candidate = CandidateResponse(
        prompt="Explain machine learning",
        response="Machine learning is a subset of AI that enables computers to learn from data",
        model="gpt-4"
    )

    # Create custom weight configuration
    weight_config = WeightConfigParser.parse_weight_string(
        "accuracy:0.4,clarity:0.3,helpfulness:0.3"
    )

    # Apply to comprehensive criteria
    base_criteria = DefaultCriteria.comprehensive()
    custom_criteria = CriteriaWeightApplier.apply_weights(base_criteria, weight_config)

    # Evaluate with custom weights
    result = await judge.evaluate_multi_criteria(
        candidate,
        custom_criteria=custom_criteria
    )

    print(f"Overall Score: {result.aggregated.overall_score:.1f}/5")
    for cs in result.criterion_scores:
        print(f"{cs.criterion_name}: {cs.score}/5 (weight: {cs.weight:.1%})")

    await judge.close()

# Run the evaluation
asyncio.run(evaluate_with_custom_weights())
```

## Weight Configuration Tips

### 1. Weight Distribution Guidelines

- **Primary criteria**: 30-50% of total weight
- **Secondary criteria**: 20-30% of total weight
- **Supporting criteria**: 10-20% of total weight
- **Total should sum to 1.0** (automatically normalized)

### 2. Common Weight Patterns

- **Accuracy-focused**: accuracy:0.4, clarity:0.3, helpfulness:0.3
- **Clarity-focused**: clarity:0.4, accuracy:0.3, helpfulness:0.3
- **Completeness-focused**: completeness:0.4, accuracy:0.3, clarity:0.3
- **Balanced**: All criteria with equal or near-equal weights

### 3. Validation

- Weights are automatically normalized to sum to 1.0
- Invalid criterion names will raise an error
- Negative weights are not allowed
- Empty weight configurations are not allowed

### 4. Performance Considerations

- Custom weights don't affect evaluation speed
- Weight parsing is very fast (microseconds)
- Configuration is cached for repeated use

## Troubleshooting

### Common Issues

1. **"Criterion 'X' not found"**

   - Check available criteria for your criteria type
   - Use `--criteria-type` to see available options

2. **"Invalid weight value"**

   - Ensure weights are numbers (can be decimals or integers)
   - Avoid negative values

3. **"Weight configuration cannot be empty"**
   - Provide at least one criterion:weight pair
   - Check for typos in the weight string

### Getting Help

```bash
# See available criteria types
python -m src.llm_judge evaluate --help

# Test with equal weights first
python -m src.llm_judge evaluate "test" "test response" --equal-weights

# Use basic criteria type for simpler testing
python -m src.llm_judge evaluate "test" "test response" --criteria-type basic --equal-weights
```
