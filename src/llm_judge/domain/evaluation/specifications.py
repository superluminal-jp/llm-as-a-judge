"""
Evaluation domain specifications.

Contains specification classes for complex business rules and queries.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from ..shared_kernel.value_objects import EntityId
from .entities import Evaluation, CriterionDefinition
from .value_objects import EvaluationType, EvaluationStatus


class EvaluationSpecification(ABC):
    """Abstract base class for evaluation specifications."""

    @abstractmethod
    def is_satisfied_by(self, evaluation: Evaluation) -> bool:
        """Check if evaluation satisfies this specification."""
        pass

    def and_specification(
        self, other: "EvaluationSpecification"
    ) -> "EvaluationSpecification":
        """Combine with another specification using AND logic."""
        return AndEvaluationSpecification(self, other)

    def or_specification(
        self, other: "EvaluationSpecification"
    ) -> "EvaluationSpecification":
        """Combine with another specification using OR logic."""
        return OrEvaluationSpecification(self, other)

    def not_specification(self) -> "EvaluationSpecification":
        """Negate this specification."""
        return NotEvaluationSpecification(self)


class CriteriaSpecification(ABC):
    """Abstract base class for criteria specifications."""

    @abstractmethod
    def is_satisfied_by(self, criteria: CriterionDefinition) -> bool:
        """Check if criteria satisfies this specification."""
        pass


class ScoringSpecification(ABC):
    """Abstract base class for scoring specifications."""

    @abstractmethod
    def is_satisfied_by(self, score: float, context: Dict[str, Any]) -> bool:
        """Check if score satisfies this specification."""
        pass


# Concrete specification implementations


class EvaluationStatusSpecification(EvaluationSpecification):
    """Specification for evaluation status."""

    def __init__(self, status: EvaluationStatus):
        self.status = status

    def is_satisfied_by(self, evaluation: Evaluation) -> bool:
        return evaluation.status == self.status


class EvaluationTypeSpecification(EvaluationSpecification):
    """Specification for evaluation type."""

    def __init__(self, evaluation_type: EvaluationType):
        self.evaluation_type = evaluation_type

    def is_satisfied_by(self, evaluation: Evaluation) -> bool:
        return evaluation.evaluation_type == self.evaluation_type


class CompletedEvaluationSpecification(EvaluationSpecification):
    """Specification for completed evaluations."""

    def is_satisfied_by(self, evaluation: Evaluation) -> bool:
        return evaluation.status == EvaluationStatus.COMPLETED


class FailedEvaluationSpecification(EvaluationSpecification):
    """Specification for failed evaluations."""

    def is_satisfied_by(self, evaluation: Evaluation) -> bool:
        return evaluation.status == EvaluationStatus.FAILED


class PendingEvaluationSpecification(EvaluationSpecification):
    """Specification for pending evaluations."""

    def is_satisfied_by(self, evaluation: Evaluation) -> bool:
        return evaluation.status == EvaluationStatus.PENDING


class CriteriaTypeSpecification(CriteriaSpecification):
    """Specification for criteria type."""

    def __init__(self, criterion_type: str):
        self.criterion_type = criterion_type

    def is_satisfied_by(self, criteria: CriterionDefinition) -> bool:
        return criteria.criterion_type.value == self.criterion_type


class WeightRangeSpecification(CriteriaSpecification):
    """Specification for weight range."""

    def __init__(self, min_weight: float, max_weight: float):
        self.min_weight = min_weight
        self.max_weight = max_weight

    def is_satisfied_by(self, criteria: CriterionDefinition) -> bool:
        return self.min_weight <= criteria.weight <= self.max_weight


class ScoreRangeSpecification(ScoringSpecification):
    """Specification for score range."""

    def __init__(self, min_score: float, max_score: float):
        self.min_score = min_score
        self.max_score = max_score

    def is_satisfied_by(self, score: float, context: Dict[str, Any]) -> bool:
        return self.min_score <= score <= self.max_score


class HighConfidenceSpecification(ScoringSpecification):
    """Specification for high confidence scores."""

    def __init__(self, min_confidence: float = 0.8):
        self.min_confidence = min_confidence

    def is_satisfied_by(self, score: float, context: Dict[str, Any]) -> bool:
        confidence = context.get("confidence", 0.0)
        return confidence >= self.min_confidence


# Composite specifications


class AndEvaluationSpecification(EvaluationSpecification):
    """AND combination of evaluation specifications."""

    def __init__(self, left: EvaluationSpecification, right: EvaluationSpecification):
        self.left = left
        self.right = right

    def is_satisfied_by(self, evaluation: Evaluation) -> bool:
        return self.left.is_satisfied_by(evaluation) and self.right.is_satisfied_by(
            evaluation
        )


class OrEvaluationSpecification(EvaluationSpecification):
    """OR combination of evaluation specifications."""

    def __init__(self, left: EvaluationSpecification, right: EvaluationSpecification):
        self.left = left
        self.right = right

    def is_satisfied_by(self, evaluation: Evaluation) -> bool:
        return self.left.is_satisfied_by(evaluation) or self.right.is_satisfied_by(
            evaluation
        )


class NotEvaluationSpecification(EvaluationSpecification):
    """NOT negation of evaluation specification."""

    def __init__(self, specification: EvaluationSpecification):
        self.specification = specification

    def is_satisfied_by(self, evaluation: Evaluation) -> bool:
        return not self.specification.is_satisfied_by(evaluation)
