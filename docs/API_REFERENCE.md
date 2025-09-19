# API Reference

## Overview

This document provides comprehensive API reference for the LLM-as-a-Judge system, including the new multi-criteria evaluation capabilities.

## Core Classes

### LLMJudge

The main class for performing evaluations.

```python
class LLMJudge:
    def __init__(self, config=None, judge_model: str = None)
```

#### Parameters

- `config` (Optional[LLMConfig]): Configuration object. If None, loads from environment/config files
- `judge_model` (Optional[str]): Specific model to use as judge. Overrides config defaults

#### Methods

##### evaluate_multi_criteria()

**NEW**: Comprehensive multi-criteria evaluation (recommended)

```python
async def evaluate_multi_criteria(
    self,
    candidate: CandidateResponse,
    criteria: Optional[EvaluationCriteria] = None,
    criteria_type: Optional[str] = None
) -> MultiCriteriaResult
```

**Parameters:**

- `candidate` (CandidateResponse): The response to evaluate
- `criteria` (Optional[EvaluationCriteria]): Custom evaluation criteria. If None, uses default criteria based on criteria_type
- `criteria_type` (Optional[str]): Type of default criteria to use ("comprehensive", "basic", "technical", "creative"). If None, uses config default

**Returns:** `MultiCriteriaResult` with detailed scores across all criteria

**Example:**

```python
judge = LLMJudge()
candidate = CandidateResponse("What is AI?", "AI is artificial intelligence", "gpt-4")

# Default comprehensive evaluation (uses config default)
result = await judge.evaluate_multi_criteria(candidate)

# Use specific criteria type
result = await judge.evaluate_multi_criteria(candidate, criteria_type="technical")
print(f"Overall Score: {result.aggregated.overall_score:.1f}/5")
print(f"Criteria Count: {len(result.criterion_scores)}")

# Access individual criterion scores
for cs in result.criterion_scores:
    print(f"{cs.criterion_name}: {cs.score}/5 - {cs.reasoning}")
```

##### evaluate_response()

Enhanced single/multi-criteria evaluation with backward compatibility

```python
async def evaluate_response(
    self,
    candidate: CandidateResponse,
    criteria: str = "overall quality",
    use_multi_criteria: bool = True
) -> EvaluationResult
```

**Parameters:**

- `candidate` (CandidateResponse): The response to evaluate
- `criteria` (str): Evaluation criteria description (used in single-criterion mode)
- `use_multi_criteria` (bool): Whether to use multi-criteria evaluation (default: True)

**Returns:** `EvaluationResult` with aggregated score and comprehensive reasoning

**Example:**

```python
# Multi-criteria evaluation (default)
result = await judge.evaluate_response(candidate)
print(f"Score: {result.score}/5")  # Weighted aggregated score
print(f"Reasoning: {result.reasoning}")  # Comprehensive reasoning

# Access multi-criteria metadata
if result.metadata.get('multi_criteria'):
    individual_scores = result.metadata['individual_scores']
    for criterion, details in individual_scores.items():
        print(f"{criterion}: {details['score']}")

# Single-criterion evaluation (legacy)
result = await judge.evaluate_response(candidate, "accuracy", use_multi_criteria=False)
```

##### compare_responses()

Compare two responses using multi-criteria analysis

```python
async def compare_responses(
    self,
    response_a: CandidateResponse,
    response_b: CandidateResponse
) -> Dict[str, Any]
```

**Parameters:**

- `response_a` (CandidateResponse): First response to compare
- `response_b` (CandidateResponse): Second response to compare

**Returns:** Dictionary with comparison results

**Example:**

```python
result = await judge.compare_responses(candidate_a, candidate_b)
print(f"Winner: {result['winner']}")  # 'A', 'B', or 'tie'
print(f"Reasoning: {result['reasoning']}")
print(f"Confidence: {result['confidence']}")
```

##### close()

Clean up resources

```python
async def close(self) -> None
```

### CandidateResponse

Represents a response to be evaluated.

```python
@dataclass
class CandidateResponse:
    prompt: str
    response: str
    model: str = "unknown"
```

**Parameters:**

- `prompt` (str): The original question or prompt
- `response` (str): The response text to evaluate
- `model` (str): Model that generated the response (default: "unknown")

### EvaluationResult

Result of single or aggregated multi-criteria evaluation.

```python
@dataclass
class EvaluationResult:
    score: float
    reasoning: str
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Attributes:**

- `score` (float): Overall evaluation score (1-5 scale)
- `reasoning` (str): Detailed reasoning for the score
- `confidence` (float): Confidence level (0.0-1.0)
- `metadata` (Dict): Additional metadata including multi-criteria details

## Multi-Criteria Domain Models

### MultiCriteriaResult

Comprehensive result of multi-criteria evaluation.

```python
@dataclass
class MultiCriteriaResult:
    # Individual criterion scores
    criterion_scores: List[CriterionScore] = field(default_factory=list)

    # Aggregated results
    aggregated: Optional[AggregatedScore] = None

    # Evaluation metadata
    criteria_used: Optional[EvaluationCriteria] = None
    evaluation_timestamp: datetime = field(default_factory=datetime.now)
    judge_model: str = "unknown"
    processing_duration: Optional[float] = None

    # Overall assessment
    overall_reasoning: str = ""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Key Methods:**

```python
def get_criterion_score(self, criterion_name: str) -> Optional[CriterionScore]
def get_scores_by_type(self, criterion_type) -> List[CriterionScore]
def get_summary(self) -> Dict[str, Any]
def to_legacy_format(self) -> Dict[str, Any]  # For backward compatibility
```

### CriterionScore

Score for a single evaluation criterion.

```python
@dataclass
class CriterionScore:
    criterion_name: str
    score: float
    reasoning: str
    confidence: float = 0.0

    # Additional metadata
    max_score: int = 5
    min_score: int = 1
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Properties:**

```python
@property
def normalized_score(self) -> float:
    """Normalize score to 0-1 range."""
    return (self.score - self.min_score) / (self.max_score - self.min_score)

@property
def weighted_score(self) -> float:
    """Get the weighted score."""
    return self.score * self.weight

@property
def percentage_score(self) -> float:
    """Get score as percentage."""
    return self.normalized_score * 100
```

### AggregatedScore

Aggregated score across multiple criteria.

```python
@dataclass
class AggregatedScore:
    overall_score: float
    weighted_score: float
    confidence: float

    # Score statistics
    mean_score: float = 0.0
    median_score: float = 0.0
    score_std: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0

    # Weighting information
    total_weight: float = 1.0
    criteria_count: int = 0
```

## Evaluation Criteria System

### EvaluationCriteria

Collection of evaluation criteria with metadata.

```python
@dataclass
class EvaluationCriteria:
    name: str
    description: str = ""
    criteria: List[CriterionDefinition] = field(default_factory=list)
    validate_weights: bool = False
    normalize_weights: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Methods:**

```python
def get_criterion(self, name: str) -> Optional[CriterionDefinition]
def get_criteria_by_type(self, criterion_type: CriterionType) -> List[CriterionDefinition]
def add_criterion(self, criterion: CriterionDefinition) -> None
@property
def total_weight(self) -> float
```

### CriterionDefinition

Definition of a single evaluation criterion.

```python
@dataclass(frozen=True)
class CriterionDefinition:
    name: str
    description: str
    criterion_type: CriterionType
    weight: float = 1.0
    scale_min: int = 1
    scale_max: int = 5
    evaluation_prompt: str = ""
    examples: Dict[int, str] = field(default_factory=dict)
```

### DefaultCriteria

Factory for creating standard criteria sets.

```python
class DefaultCriteria:
    @classmethod
    def comprehensive(cls) -> EvaluationCriteria:
        """7-dimension comprehensive evaluation."""

    @classmethod
    def basic(cls) -> EvaluationCriteria:
        """4-dimension basic evaluation."""

    @classmethod
    def technical(cls) -> EvaluationCriteria:
        """Technical content evaluation."""

    @classmethod
    def creative(cls) -> EvaluationCriteria:
        """Creative content evaluation."""

    @classmethod
    def builder(cls) -> 'CriteriaBuilder':
        """Builder pattern for custom criteria."""
```

**Example:**

```python
# Use predefined criteria sets
comprehensive = DefaultCriteria.comprehensive()  # 7 criteria
basic = DefaultCriteria.basic()  # 4 criteria
technical = DefaultCriteria.technical()  # Technical focus

# Custom criteria with builder
custom = (DefaultCriteria.builder()
         .add_accuracy(weight=0.4)
         .add_clarity(weight=0.3)
         .add_relevance(weight=0.3)
         .build("custom_evaluation", "Custom 3-criteria evaluation"))
```

### CriterionType

Enumeration of criterion types.

```python
class CriterionType(Enum):
    FACTUAL = "factual"           # Objective, verifiable accuracy
    QUALITATIVE = "qualitative"   # Subjective quality aspects
    STRUCTURAL = "structural"     # Organization and formatting
    CONTEXTUAL = "contextual"     # Context appropriateness
    LINGUISTIC = "linguistic"     # Language quality
    ETHICAL = "ethical"           # Ethical considerations
```

## Batch Processing API

### BatchProcessingService

Service for handling batch evaluations with multi-criteria support.

```python
class BatchProcessingService:
    def __init__(self, llm_judge: LLMJudge, max_workers: int = 10)
```

#### Methods

```python
async def process_batch_from_file(
    self,
    file_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    batch_config: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable[[BatchProgress], None]] = None
) -> BatchResult
```

**Parameters:**

- `file_path`: Path to input file (JSONL, CSV, or JSON)
- `output_path`: Optional path for output file
- `batch_config`: Batch configuration options
- `progress_callback`: Optional progress tracking callback

**Returns:** `BatchResult` with comprehensive statistics

**Example:**

```python
from src.llm_judge import BatchProcessingService, LLMJudge

judge = LLMJudge()
batch_service = BatchProcessingService(judge, max_workers=10)

# Progress callback
def progress_callback(progress):
    print(f"Progress: {progress.completion_percentage:.1%}")

# Process batch file
result = await batch_service.process_batch_from_file(
    "evaluations.jsonl",
    output_path="results.json",
    batch_config={
        "max_concurrent_items": 10,
        "retry_failed_items": True,
        "max_retries_per_item": 3
    },
    progress_callback=progress_callback
)

print(f"Success rate: {result.success_rate:.1%}")
print(f"Processing time: {result.processing_duration:.1f}s")
```

## Configuration

### LLMConfig

Configuration for LLM providers and behavior.

```python
@dataclass
class LLMConfig:
    # API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # Provider Settings
    default_provider: str = "anthropic"
    openai_model: str = "gpt-4"
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Request Settings
    request_timeout: int = 30
    connect_timeout: int = 10
    max_retries: int = 3

    # Logging
    log_level: str = "INFO"
    enable_audit_logging: bool = False
```

**Loading Configuration:**

```python
from src.llm_judge.infrastructure.config.config import load_config

# Load from environment/.env file
config = load_config()

# Create custom config
config = LLMConfig(
    anthropic_api_key="your-key",
    default_provider="anthropic",
    anthropic_model="claude-sonnet-4-20250514"
)

judge = LLMJudge(config=config)
```

## Error Handling

### Exception Types

```python
# Configuration errors
class ConfigurationError(Exception): pass

# LLM client errors
class LLMClientError(Exception): pass

# Evaluation errors
class EvaluationError(Exception): pass

# Batch processing errors
class BatchProcessingError(Exception): pass
```

### Error Classification

The system automatically classifies and handles different types of errors:

1. **Transient errors**: Automatically retried with backoff
2. **Authentication errors**: Immediately reported
3. **Rate limit errors**: Handled with backoff and retry
4. **Parsing errors**: Fallback to mock or degraded responses
5. **Network errors**: Circuit breaker and fallback patterns
6. **Validation errors**: Clear error messages with correction guidance

## Usage Patterns

### Basic Multi-Criteria Evaluation

```python
import asyncio
from src.llm_judge import LLMJudge, CandidateResponse

async def basic_evaluation():
    judge = LLMJudge()

    candidate = CandidateResponse(
        prompt="What is machine learning?",
        response="Machine learning is a subset of AI that enables computers to learn from data",
        model="gpt-4"
    )

    # Multi-criteria evaluation
    result = await judge.evaluate_multi_criteria(candidate)

    print(f"Overall Score: {result.aggregated.overall_score:.1f}/5")
    print(f"Number of criteria: {len(result.criterion_scores)}")

    # Show top and bottom scoring criteria
    sorted_scores = sorted(result.criterion_scores, key=lambda x: x.score, reverse=True)
    print(f"Highest: {sorted_scores[0].criterion_name} ({sorted_scores[0].score}/5)")
    print(f"Lowest: {sorted_scores[-1].criterion_name} ({sorted_scores[-1].score}/5)")

    await judge.close()

asyncio.run(basic_evaluation())
```

### Custom Criteria Evaluation

```python
from src.llm_judge.domain.evaluation.criteria import EvaluationCriteria, CriterionDefinition, CriterionType

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

### Batch Processing with Progress Tracking

```python
from src.llm_judge import BatchProcessingService, LLMJudge

async def batch_with_progress():
    judge = LLMJudge()
    batch_service = BatchProcessingService(judge, max_workers=5)

    # Progress tracking
    def progress_callback(progress):
        completed = progress.completed_items + progress.failed_items
        percentage = (completed / progress.total_items) * 100
        print(f"Progress: {percentage:.1f}% ({completed}/{progress.total_items})")
        print(f"Success: {progress.completed_items}, Failed: {progress.failed_items}")

    result = await batch_service.process_batch_from_file(
        "large_evaluation_set.jsonl",
        output_path="detailed_results.json",
        batch_config={
            "max_concurrent_items": 8,
            "retry_failed_items": True,
            "max_retries_per_item": 2,
            "continue_on_error": True
        },
        progress_callback=progress_callback
    )

    print(f"\\nBatch completed:")
    print(f"Success rate: {result.success_rate:.1%}")
    print(f"Total time: {result.processing_duration:.1f}s")
    print(f"Average time per item: {result.average_processing_time:.2f}s")

    await judge.close()

asyncio.run(batch_with_progress())
```

## Migration Guide

### From Single-Criterion to Multi-Criteria

Old code continues to work but gets enhanced results:

```python
# Old way (still works, but now returns multi-criteria results)
result = await judge.evaluate_response(candidate, "overall quality")
print(result.score)  # Now aggregated multi-criteria score
print(result.reasoning)  # Now comprehensive reasoning

# New way (explicit multi-criteria)
multi_result = await judge.evaluate_multi_criteria(candidate)
print(multi_result.aggregated.overall_score)  # Same score
print(multi_result.overall_reasoning)  # Same reasoning

# Access individual criteria (new capability)
for cs in multi_result.criterion_scores:
    print(f"{cs.criterion_name}: {cs.score}/5")
```

### Enabling Single-Criterion Mode

For scenarios where you need the original single-criterion behavior:

```python
# Explicit single-criterion mode
result = await judge.evaluate_response(
    candidate,
    "accuracy and completeness",
    use_multi_criteria=False
)
# This bypasses multi-criteria evaluation
```

### Batch File Compatibility

Existing batch files work unchanged but now produce multi-criteria results:

```jsonl
{
  "type": "single",
  "prompt": "What is AI?",
  "response": "AI is artificial intelligence",
  "model": "gpt-4"
}
```

The output format is enhanced but backward compatible:

```json
{
  "result": {
    "score": 3.8,
    "reasoning": "Comprehensive multi-criteria analysis shows...",
    "confidence": 0.91,
    "metadata": {
      "multi_criteria": true,
      "criteria_count": 7,
      "individual_scores": {
        "accuracy": { "score": 4.0, "reasoning": "Factually correct" },
        "clarity": { "score": 4.5, "reasoning": "Very clear" }
      }
    }
  }
}
```

## CLI Reference

### Command Line Interface

The LLM-as-a-Judge system provides a command-line interface for easy evaluation and comparison.

#### Basic Usage

```bash
# Evaluate a single response (uses comprehensive criteria by default)
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence"

# Use specific criteria type
python -m src.llm_judge evaluate "What is AI?" "AI is artificial intelligence" --criteria-type basic

# Use technical criteria for technical content
python -m src.llm_judge evaluate "Explain ML" "Machine learning is..." --criteria-type technical

# Compare two responses
python -m src.llm_judge compare "Explain ML" "Basic explanation" "Detailed explanation"

# Output as JSON
python -m src.llm_judge evaluate "Question" "Answer" --output json
```

#### CLI Options

**Global Options:**

- `--provider {openai,anthropic,bedrock}`: LLM provider to use as judge
- `--judge-model MODEL`: Specific model to use as judge
- `--config PATH`: Path to configuration file
- `--output {text,json}`: Output format (default: text)
- `--verbose, -v`: Enable verbose output

**Evaluate Command Options:**

- `--criteria CRITERIA`: Evaluation criteria (default: "overall quality")
- `--model MODEL`: Model that generated the response
- `--criteria-type {comprehensive,basic,technical,creative}`: Type of default criteria to use
- `--show-detailed`: Show detailed multi-criteria breakdown

**Compare Command Options:**

- `--model-a MODEL`: Model that generated response A
- `--model-b MODEL`: Model that generated response B

#### Environment Variables

Set these in your `.env` file or environment:

```bash
# Default criteria type
DEFAULT_CRITERIA_TYPE=comprehensive

# LLM Provider API Keys
OPENAI_API_KEY=sk-your-openai-api-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# Default Provider
DEFAULT_PROVIDER=anthropic
```
