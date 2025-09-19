# Multi-Criteria Evaluation Guide

## Overview

The LLM-as-a-Judge system provides comprehensive multi-criteria evaluation by default, analyzing responses across 7 key dimensions to provide detailed, actionable feedback. This guide explains how to use and customize the multi-criteria evaluation system.

## Default Evaluation Criteria

### 7-Dimension Analysis with Equal Weights

The system evaluates responses across these 7 criteria with **equal weights by default**:

| Criterion           | Weight | Scale | Description                                         |
| ------------------- | ------ | ----- | --------------------------------------------------- |
| **Accuracy**        | 14.3%  | 1-5   | Factual correctness and truthfulness of information |
| **Completeness**    | 14.3%  | 1-5   | Depth and comprehensiveness of coverage             |
| **Clarity**         | 14.3%  | 1-5   | Clarity of expression and ease of understanding     |
| **Relevance**       | 14.3%  | 1-5   | Direct relevance to the question asked              |
| **Helpfulness**     | 14.3%  | 1-5   | Practical value and usefulness to the reader        |
| **Coherence**       | 14.3%  | 1-5   | Logical flow and internal consistency               |
| **Appropriateness** | 14.3%  | 1-5   | Tone, style, and contextual appropriateness         |

### Scoring System

- **Scale**: Each criterion is scored from 1-5
- **Weighting**: All criteria have equal importance (14.3% each for comprehensive evaluation)
- **Aggregation**: Final score is calculated as weighted average across all criteria
- **Confidence**: Each criterion score includes a confidence level (0-100%)

## Custom Criteria and Weight Configuration

### Overview

By default, the system uses **equal weights** for all criteria in each criteria type. This ensures that no single criterion dominates the evaluation. However, you can customize both the criteria themselves and their weights to create evaluation frameworks tailored to your specific needs.

### Custom Criteria Definition

You can define completely custom criteria sets with your own evaluation dimensions, prompts, and examples. This is particularly useful for domain-specific evaluations or specialized use cases.

#### 1. Custom Criteria via CLI

Define criteria directly in the command line:

```bash
# Define custom criteria with detailed specifications
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence" \
  --custom-criteria "accuracy:Factual correctness and truthfulness:factual:0.4,clarity:How clear and understandable the response is:linguistic:0.3,helpfulness:How useful the response is for the user:qualitative:0.3"
```

**Format**: `name:description:type:weight,name2:description2:type2:weight2`

#### 2. Custom Criteria from File

Create a JSON file with detailed criteria definitions:

```bash
# Use criteria from JSON file
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence" \
  --criteria-file ./my-criteria.json
```

**JSON Format**:

```json
{
  "name": "Custom Evaluation Criteria",
  "description": "Custom criteria for specific use case",
  "criteria": [
    {
      "name": "accuracy",
      "description": "Factual correctness and truthfulness",
      "criterion_type": "factual",
      "weight": 1.0,
      "evaluation_prompt": "Evaluate the factual accuracy of the response. Are the claims correct and verifiable?",
      "examples": {
        "1": "Contains major factual errors",
        "2": "Some factual inaccuracies present",
        "3": "Mostly accurate with minor errors",
        "4": "Accurate with no significant issues",
        "5": "Completely accurate and well-supported"
      },
      "domain_specific": false,
      "requires_context": false,
      "metadata": {
        "importance": "high",
        "category": "content_quality"
      }
    }
  ]
}
```

#### 3. Create Criteria Template

Generate a template file to get started:

```bash
# Create a criteria template
python -m src.llm_judge create-criteria-template my-criteria.json \
  --name "Academic Evaluation" \
  --description "Criteria for academic content evaluation"
```

#### 4. List Available Criteria Types

See all available criterion types:

```bash
# List available criterion types
python -m src.llm_judge evaluate --list-criteria-types
```

Available types: `factual`, `qualitative`, `structural`, `contextual`, `linguistic`, `ethical`

### Weight Configuration Options

#### 1. Custom Weights via CLI

Use the `--criteria-weights` argument to specify custom weights:

```bash
# Emphasize accuracy and clarity
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence" \
  --criteria-weights "accuracy:0.4,clarity:0.3,helpfulness:0.2,relevance:0.1"

# Focus on completeness and coherence
python -m src.llm_judge evaluate "Explain ML" "Machine learning is..." \
  --criteria-weights "completeness:0.5,coherence:0.3,clarity:0.2"
```

**Weight Format**: `criterion1:weight1,criterion2:weight2,criterion3:weight3`

- Weights are automatically normalized to sum to 1.0
- Available criteria depend on the criteria type (comprehensive, basic, technical, creative)
- Weights can be specified as decimals (0.3) or integers (3)

#### 2. Equal Weights

Use the `--equal-weights` flag to give all criteria equal importance:

```bash
# All criteria get equal weight (1/n where n is number of criteria)
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence" --equal-weights
```

#### 3. Configuration File

Set default weight configuration in your config file:

```json
{
  "default_provider": "openai",
  "default_criteria_type": "comprehensive",
  "criteria_weights": "accuracy:0.3,clarity:0.25,helpfulness:0.25,completeness:0.2",
  "use_equal_weights": false
}
```

### Available Criteria by Type

#### Comprehensive (7 criteria)

- `accuracy` - Factual correctness and truthfulness
- `completeness` - Thoroughness of coverage
- `clarity` - Clarity of expression
- `relevance` - Relevance to the prompt
- `helpfulness` - Practical value
- `coherence` - Logical flow and consistency
- `appropriateness` - Tone and style appropriateness

#### Basic (3 criteria)

- `accuracy` - Factual correctness
- `clarity` - Clarity and understandability
- `helpfulness` - Usefulness to the user

#### Technical (5 criteria)

- `technical_accuracy` - Technical correctness
- `implementation_feasibility` - Practical implementability
- `best_practices` - Adherence to standards
- `completeness` - Thoroughness of explanation
- `clarity` - Technical clarity

#### Creative (5 criteria)

- `creativity` - Originality and creative value
- `engagement` - How engaging the content is
- `coherence` - Internal consistency
- `relevance` - Relevance to the theme
- `style` - Writing style and quality

### Examples

#### Example 1: Academic Evaluation with Custom Criteria

For academic content, use specialized criteria:

```bash
# Use academic criteria from file
python -m src.llm_judge evaluate "Explain quantum computing" "Quantum computing uses..." \
  --criteria-file examples/academic_criteria.json

# Or define custom academic criteria
python -m src.llm_judge evaluate "Explain quantum computing" "Quantum computing uses..." \
  --custom-criteria "accuracy:Factual correctness and truthfulness:factual:0.3,completeness:Thoroughness of coverage:qualitative:0.3,clarity:Clarity of expression:linguistic:0.2,relevance:Relevance to the prompt:contextual:0.2"
```

#### Example 2: Creative Writing

For creative content, emphasize creativity and engagement:

```bash
python -m src.llm_judge evaluate "Write a story about AI" "Once upon a time..." \
  --criteria-type creative \
  --criteria-weights "creativity:0.4,engagement:0.3,coherence:0.2,style:0.1"
```

#### Example 3: Technical Documentation with Custom Criteria

For technical documentation, use specialized technical criteria:

```bash
# Use technical criteria from file
python -m src.llm_judge evaluate "Document this API" "This API provides..." \
  --criteria-file examples/technical_criteria.json

# Or define custom technical criteria
python -m src.llm_judge evaluate "Document this API" "This API provides..." \
  --custom-criteria "technical_accuracy:Correctness of technical information:factual:0.4,implementation_feasibility:Whether solutions are implementable:contextual:0.3,clarity:Technical clarity and understandability:linguistic:0.3"
```

### Programmatic Custom Criteria Configuration

```python
from src.llm_judge import LLMJudge, CandidateResponse
from src.llm_judge.domain.evaluation.custom_criteria import (
    CustomCriteriaBuilder,
    CustomCriteriaParser
)
from src.llm_judge.domain.evaluation.weight_config import WeightConfigParser, CriteriaWeightApplier

async def evaluate_with_custom_criteria():
    judge = LLMJudge()

    candidate = CandidateResponse(
        prompt="Explain machine learning",
        response="Machine learning is a subset of AI...",
        model="gpt-4"
    )

    # Method 1: Build custom criteria programmatically
    builder = CustomCriteriaBuilder()
    builder.add_criterion(
        name="accuracy",
        description="Factual correctness and truthfulness",
        criterion_type="factual",
        weight=0.4,
        evaluation_prompt="Evaluate the factual accuracy of the response.",
        examples={1: "Contains errors", 5: "Completely accurate"}
    )
    builder.add_criterion(
        name="clarity",
        description="How clear and understandable the response is",
        criterion_type="linguistic",
        weight=0.3
    )
    builder.add_criterion(
        name="helpfulness",
        description="How useful the response is for the user",
        criterion_type="qualitative",
        weight=0.3
    )

    custom_criteria = builder.build()

    # Method 2: Parse from string
    criteria_string = "accuracy:Factual correctness:factual:0.4,clarity:How clear the response is:linguistic:0.3,helpfulness:How useful the response is:qualitative:0.3"
    criteria_definitions = CustomCriteriaParser.parse_criteria_string(criteria_string)

    builder2 = CustomCriteriaBuilder()
    for cd in criteria_definitions:
        builder2.add_criterion(
            name=cd.name,
            description=cd.description,
            criterion_type=cd.criterion_type,
            weight=cd.weight
        )
    custom_criteria2 = builder2.build()

    # Evaluate with custom criteria
    result = await judge.evaluate_multi_criteria(
        candidate,
        custom_criteria=custom_criteria
    )

    print(f"Overall Score: {result.aggregated.overall_score:.1f}/5")
    for cs in result.criterion_scores:
        print(f"{cs.criterion_name}: {cs.score}/5 (weight: {cs.weight:.1%})")
```

## Using Multi-Criteria Evaluation

### CLI Usage

```bash
# Default multi-criteria evaluation
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence"

# Show detailed breakdown
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence" --show-detailed

# JSON output with all criterion details
python -m src.llm_judge --output json evaluate "What is AI?" "AI is artificial intelligence"

# Use custom criteria weights
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence" --criteria-weights "accuracy:0.4,clarity:0.3,helpfulness:0.3"

# Use equal weights for all criteria
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence" --equal-weights

# Batch processing (all items use multi-criteria)
python -m src.llm_judge batch evaluations.jsonl --output results.json
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
python -m src.llm_judge batch evaluations.jsonl --output detailed_results.json

# High concurrency batch processing
python -m src.llm_judge batch large_dataset.jsonl --max-concurrent 20 --output results.json

# Batch with progress tracking
python -m src.llm_judge batch evaluations.jsonl --batch-name "Model Evaluation Study"
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
            "accuracy": { "score": 4.0, "reasoning": "Factually correct" },
            "clarity": { "score": 4.5, "reasoning": "Very clear explanation" }
          }
        }
      }
    }
  ]
}
```

## Backward Compatibility

### Basic Criteria Mode

For users who prefer simpler evaluation with fewer criteria:

```bash
# Use basic criteria type for simpler evaluation
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence" --criteria-type basic

# Programmatic basic criteria
result = await judge.evaluate_multi_criteria(candidate, criteria_type="basic")
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
python -m src.llm_judge --verbose evaluate "Question" "Answer"

# Check system status
python -m src.llm_judge --help
```

### Getting Help

- Check the main README.md for setup and configuration
- Review the CLI help: `python -m src.llm_judge --help`
- Examine batch result files for detailed error information
- Enable verbose mode for detailed logging

## Best Practices

### When to Use Multi-Criteria

- **High-stakes evaluations**: When you need comprehensive analysis
- **Model comparison**: Comparing different AI systems across multiple dimensions
- **Quality assessment**: Understanding specific strengths and weaknesses
- **Research applications**: When detailed metrics are needed

### When to Use Basic Criteria

- **High-volume processing**: When speed is more important than comprehensiveness
- **Simple evaluations**: When you only need basic quality assessment
- **Resource constraints**: When you want to minimize API costs and processing time

### Optimization Tips

1. **Use appropriate criteria**: Choose criteria sets that match your evaluation needs
2. **Leverage batch processing**: Process multiple items concurrently
3. **Monitor costs**: Track API usage and costs for budget management
4. **Cache results**: Avoid re-evaluating identical inputs
5. **Use JSON output**: For programmatic processing and analysis
