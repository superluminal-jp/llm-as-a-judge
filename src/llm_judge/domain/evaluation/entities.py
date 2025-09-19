"""
Entities for the Evaluation Bounded Context.

Entities are objects that have a distinct identity and lifecycle.
They encapsulate business logic and maintain invariants.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from ..shared_kernel.value_objects import (
    EntityId,
    Timestamp,
    EvaluationId,
    ModelName,
    ProviderName,
)
from ..shared_kernel.domain_events import (
    DomainEvent,
    EvaluationCompleted,
    EvaluationFailed,
)
from .value_objects import (
    EvaluationType,
    EvaluationStatus,
    EvaluationMetadata,
    EvaluationPrompt,
    EvaluationResponse,
    EvaluationCriteria,
    EvaluationResult,
)


@dataclass(frozen=True)
class CriterionDefinition:
    """Entity representing a single evaluation criterion."""

    name: str
    description: str
    id: EntityId = field(default_factory=EntityId)
    weight: float = 1.0
    scale_min: int = 1
    scale_max: int = 5
    evaluation_prompt: str = ""
    examples: Dict[int, str] = field(default_factory=dict)
    domain_specific: bool = False
    requires_context: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Timestamp = field(default_factory=Timestamp)
    updated_at: Timestamp = field(default_factory=Timestamp)

    def __post_init__(self):
        """Validate criterion definition."""
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Criterion name must be a non-empty string")
        if len(self.name) > 100:
            raise ValueError("Criterion name must be less than 100 characters")

        if not self.description or not isinstance(self.description, str):
            raise ValueError("Criterion description must be a non-empty string")
        if len(self.description) > 500:
            raise ValueError("Criterion description must be less than 500 characters")

        if not isinstance(self.weight, (int, float)) or self.weight <= 0:
            raise ValueError("Weight must be a positive number")

        if not isinstance(self.scale_min, int) or not isinstance(self.scale_max, int):
            raise ValueError("Scale values must be integers")
        if self.scale_min >= self.scale_max:
            raise ValueError("Scale minimum must be less than maximum")
        if self.scale_min < 1 or self.scale_max > 10:
            raise ValueError("Scale values must be between 1 and 10")

    @property
    def scale_range(self) -> int:
        """Get the scale range."""
        return self.scale_max - self.scale_min + 1

    def get_example_for_score(self, score: int) -> Optional[str]:
        """Get example text for a specific score."""
        return self.examples.get(score)

    def update_weight(self, new_weight: float) -> "CriterionDefinition":
        """Create a new criterion with updated weight."""
        if not isinstance(new_weight, (int, float)) or new_weight <= 0:
            raise ValueError("Weight must be a positive number")

        return CriterionDefinition(
            id=self.id,
            name=self.name,
            description=self.description,
            weight=new_weight,
            scale_min=self.scale_min,
            scale_max=self.scale_max,
            evaluation_prompt=self.evaluation_prompt,
            examples=self.examples,
            domain_specific=self.domain_specific,
            requires_context=self.requires_context,
            metadata=self.metadata,
            created_at=self.created_at,
            updated_at=Timestamp(),
        )


@dataclass(frozen=True)
class CriterionScore:
    """Entity representing a score for a specific criterion."""

    criterion_name: str
    score: int
    reasoning: str
    confidence: float = 0.0
    max_score: int = 5
    min_score: int = 1
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate criterion score."""
        if not self.criterion_name or not isinstance(self.criterion_name, str):
            raise ValueError("Criterion name must be a non-empty string")

        if not isinstance(self.score, int):
            raise ValueError("Score must be an integer")
        if not self.min_score <= self.score <= self.max_score:
            raise ValueError(
                f"Score {self.score} must be between {self.min_score} and {self.max_score}"
            )

        if not self.reasoning or not isinstance(self.reasoning, str):
            raise ValueError("Reasoning must be a non-empty string")
        if len(self.reasoning) > 2000:
            raise ValueError("Reasoning must be less than 2000 characters")

        if not isinstance(self.confidence, (int, float)):
            raise ValueError("Confidence must be a number")
        if not 0 <= self.confidence <= 1:
            raise ValueError("Confidence must be between 0 and 1")

        if not isinstance(self.weight, (int, float)) or self.weight <= 0:
            raise ValueError("Weight must be a positive number")

    @property
    def normalized_score(self) -> float:
        """Normalize score to 0-1 range."""
        return float(self.score - self.min_score) / float(
            self.max_score - self.min_score
        )

    @property
    def weighted_score(self) -> float:
        """Get the weighted score."""
        return float(self.score) * self.weight

    @property
    def percentage_score(self) -> float:
        """Get score as percentage."""
        return self.normalized_score * 100


@dataclass(frozen=True)
class AggregatedScore:
    """Entity representing aggregated scores across multiple criteria."""

    overall_score: float
    weighted_score: float
    confidence: float
    mean_score: float = 0.0
    median_score: float = 0.0
    score_std: float = 0.0
    min_score: int = 0
    max_score: int = 0
    total_weight: float = 1.0
    criteria_count: int = 0

    def __post_init__(self):
        """Validate aggregated score."""
        if not isinstance(self.overall_score, (int, float)):
            raise ValueError("Overall score must be a number")
        if not 1 <= self.overall_score <= 5:
            raise ValueError("Overall score must be between 1 and 5")

        if not isinstance(self.confidence, (int, float)):
            raise ValueError("Confidence must be a number")
        if not 0 <= self.confidence <= 1:
            raise ValueError("Confidence must be between 0 and 1")

        if not isinstance(self.criteria_count, int) or self.criteria_count < 0:
            raise ValueError("Criteria count must be a non-negative integer")

    @property
    def is_high_confidence(self) -> bool:
        """Check if the aggregated score has high confidence."""
        return self.confidence > 0.8

    @property
    def is_low_confidence(self) -> bool:
        """Check if the aggregated score has low confidence."""
        return self.confidence < 0.3


@dataclass
class MultiCriteriaResult:
    """Entity representing the result of a multi-criteria evaluation."""

    evaluation_id: EvaluationId
    criterion_scores: List[CriterionScore] = field(default_factory=list)
    aggregated: Optional[AggregatedScore] = None
    criteria_used: Optional[List[CriterionDefinition]] = None
    evaluation_timestamp: Timestamp = field(default_factory=Timestamp)
    judge_model: ModelName = field(default_factory=lambda: ModelName("unknown"))
    processing_duration: Optional[float] = None
    overall_reasoning: str = ""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Calculate aggregated scores if not provided."""
        if self.criterion_scores and not self.aggregated:
            self.aggregated = self._calculate_aggregated_score()

    def _calculate_aggregated_score(self) -> AggregatedScore:
        """Calculate aggregated score from individual criterion scores."""
        if not self.criterion_scores:
            raise ValueError(
                "Cannot calculate aggregated score without criterion scores"
            )

        import statistics

        scores = [float(cs.score) for cs in self.criterion_scores]
        weights = [cs.weight for cs in self.criterion_scores]
        confidences = [cs.confidence for cs in self.criterion_scores]

        # Calculate weighted score
        weighted_score = sum(score * weight for score, weight in zip(scores, weights))
        total_weight = sum(weights)

        if total_weight > 0:
            weighted_score = weighted_score / total_weight
        else:
            weighted_score = sum(scores) / len(scores)

        # Calculate statistics
        mean_score = statistics.mean(scores)
        median_score = statistics.median(scores)
        score_std = statistics.stdev(scores) if len(scores) > 1 else 0.0
        min_score = int(min(scores))
        max_score = int(max(scores))

        # Calculate overall confidence (weighted average)
        if confidences and total_weight > 0:
            overall_confidence = (
                sum(conf * weight for conf, weight in zip(confidences, weights))
                / total_weight
            )
        else:
            overall_confidence = statistics.mean(confidences) if confidences else 0.0

        return AggregatedScore(
            overall_score=weighted_score,
            weighted_score=weighted_score,
            confidence=overall_confidence,
            mean_score=mean_score,
            median_score=median_score,
            score_std=score_std,
            min_score=min_score,
            max_score=max_score,
            total_weight=total_weight,
            criteria_count=len(self.criterion_scores),
        )

    def get_criterion_score(self, criterion_name: str) -> Optional[CriterionScore]:
        """Get score for a specific criterion."""
        return next(
            (cs for cs in self.criterion_scores if cs.criterion_name == criterion_name),
            None,
        )

    def add_criterion_score(self, criterion_score: CriterionScore):
        """Add a criterion score and recalculate aggregated score."""
        # Check for duplicates
        if self.get_criterion_score(criterion_score.criterion_name):
            raise ValueError(
                f"Criterion '{criterion_score.criterion_name}' already has a score"
            )

        self.criterion_scores.append(criterion_score)
        self.aggregated = self._calculate_aggregated_score()

    @property
    def is_complete(self) -> bool:
        """Check if all criteria have been scored."""
        if not self.criteria_used:
            return len(self.criterion_scores) > 0

        expected_criteria = {c.name for c in self.criteria_used}
        actual_criteria = {cs.criterion_name for cs in self.criterion_scores}

        return expected_criteria.issubset(actual_criteria)

    @property
    def missing_criteria(self) -> List[str]:
        """Get list of criteria that haven't been scored yet."""
        if not self.criteria_used:
            return []

        expected_criteria = {c.name for c in self.criteria_used}
        actual_criteria = {cs.criterion_name for cs in self.criterion_scores}

        return list(expected_criteria - actual_criteria)


@dataclass
class Evaluation:
    """Root entity for an evaluation."""

    evaluation_type: EvaluationType
    prompt: EvaluationPrompt
    response: EvaluationResponse
    id: EvaluationId = field(default_factory=EvaluationId)
    status: EvaluationStatus = EvaluationStatus.PENDING
    criteria: List[CriterionDefinition] = field(default_factory=list)
    result: Optional[MultiCriteriaResult] = None
    metadata: EvaluationMetadata = field(default_factory=EvaluationMetadata)
    created_at: Timestamp = field(default_factory=Timestamp)
    updated_at: Timestamp = field(default_factory=Timestamp)
    completed_at: Optional[Timestamp] = None
    error_message: Optional[str] = None

    def start_evaluation(self) -> None:
        """Start the evaluation process."""
        if self.status != EvaluationStatus.PENDING:
            raise ValueError(f"Cannot start evaluation in status: {self.status}")

        self.status = EvaluationStatus.IN_PROGRESS
        self.updated_at = Timestamp()

    def complete_evaluation(self, result: MultiCriteriaResult) -> None:
        """Complete the evaluation with results."""
        if self.status != EvaluationStatus.IN_PROGRESS:
            raise ValueError(f"Cannot complete evaluation in status: {self.status}")

        self.result = result
        self.status = EvaluationStatus.COMPLETED
        self.completed_at = Timestamp()
        self.updated_at = Timestamp()

        # Publish domain event
        from ..shared_kernel.domain_events import (
            publish_domain_event,
            EvaluationCompleted,
        )

        publish_domain_event(
            EvaluationCompleted(
                evaluation_id=self.id,
                score=result.aggregated.overall_score if result.aggregated else 0.0,
                confidence=result.aggregated.confidence if result.aggregated else 0.0,
                criteria_count=len(result.criterion_scores),
                processing_duration_ms=result.processing_duration or 0.0,
                provider="unknown",  # Will be set by application layer
                model=str(result.judge_model),
            )
        )

    def fail_evaluation(self, error_message: str) -> None:
        """Mark evaluation as failed."""
        if self.status not in [EvaluationStatus.PENDING, EvaluationStatus.IN_PROGRESS]:
            raise ValueError(f"Cannot fail evaluation in status: {self.status}")

        self.status = EvaluationStatus.FAILED
        self.error_message = error_message
        self.completed_at = Timestamp()
        self.updated_at = Timestamp()

        # Publish domain event
        from ..shared_kernel.domain_events import publish_domain_event, EvaluationFailed

        publish_domain_event(
            EvaluationFailed(
                evaluation_id=self.id,
                error_type="EVALUATION_ERROR",
                error_message=error_message,
                provider="unknown",  # Will be set by application layer
                model=str(self.response.model),
            )
        )

    def cancel_evaluation(self) -> None:
        """Cancel the evaluation."""
        if self.status not in [EvaluationStatus.PENDING, EvaluationStatus.IN_PROGRESS]:
            raise ValueError(f"Cannot cancel evaluation in status: {self.status}")

        self.status = EvaluationStatus.CANCELLED
        self.completed_at = Timestamp()
        self.updated_at = Timestamp()

    @property
    def is_completed(self) -> bool:
        """Check if evaluation is completed."""
        return self.status == EvaluationStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if evaluation failed."""
        return self.status == EvaluationStatus.FAILED

    @property
    def is_cancelled(self) -> bool:
        """Check if evaluation was cancelled."""
        return self.status == EvaluationStatus.CANCELLED

    @property
    def is_in_progress(self) -> bool:
        """Check if evaluation is in progress."""
        return self.status == EvaluationStatus.IN_PROGRESS

    @property
    def is_pending(self) -> bool:
        """Check if evaluation is pending."""
        return self.status == EvaluationStatus.PENDING
