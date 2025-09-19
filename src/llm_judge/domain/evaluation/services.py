"""
Evaluation domain services.

Contains domain services that encapsulate business logic for evaluation operations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from ..shared_kernel.value_objects import EntityId, Timestamp
from .entities import (
    Evaluation,
    CriterionDefinition,
    CriterionScore,
    MultiCriteriaResult,
)
from .value_objects import EvaluationType, EvaluationStatus


class EvaluationService(ABC):
    """Abstract service for evaluation operations."""

    @abstractmethod
    async def create_evaluation(
        self,
        evaluation_type: EvaluationType,
        prompt: str,
        response: str,
        criteria: List[CriterionDefinition],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Evaluation:
        """Create a new evaluation."""
        pass

    @abstractmethod
    async def start_evaluation(self, evaluation_id: EntityId) -> None:
        """Start an evaluation process."""
        pass

    @abstractmethod
    async def complete_evaluation(
        self,
        evaluation_id: EntityId,
        result: MultiCriteriaResult,
    ) -> None:
        """Complete an evaluation with results."""
        pass

    @abstractmethod
    async def fail_evaluation(
        self,
        evaluation_id: EntityId,
        error_message: str,
    ) -> None:
        """Mark an evaluation as failed."""
        pass


class CriteriaService(ABC):
    """Abstract service for criteria operations."""

    @abstractmethod
    async def validate_criteria(
        self,
        criteria: List[CriterionDefinition],
    ) -> bool:
        """Validate criteria configuration."""
        pass

    @abstractmethod
    async def normalize_weights(
        self,
        criteria: List[CriterionDefinition],
    ) -> List[CriterionDefinition]:
        """Normalize criteria weights to sum to 1.0."""
        pass


class ScoringService(ABC):
    """Abstract service for scoring operations."""

    @abstractmethod
    async def calculate_weighted_score(
        self,
        criterion_scores: List[CriterionScore],
    ) -> float:
        """Calculate weighted score from criterion scores."""
        pass

    @abstractmethod
    async def calculate_confidence(
        self,
        criterion_scores: List[CriterionScore],
    ) -> float:
        """Calculate confidence score from criterion scores."""
        pass

    @abstractmethod
    async def normalize_score(
        self,
        score: float,
        min_score: float,
        max_score: float,
    ) -> float:
        """Normalize score to 0-1 range."""
        pass


class MultiCriteriaEvaluationService(ABC):
    """Abstract service for multi-criteria evaluation operations."""

    @abstractmethod
    async def evaluate_multi_criteria(
        self,
        evaluation: Evaluation,
    ) -> MultiCriteriaResult:
        """Perform multi-criteria evaluation."""
        pass

    @abstractmethod
    async def aggregate_scores(
        self,
        criterion_scores: List[CriterionScore],
    ) -> MultiCriteriaResult:
        """Aggregate individual criterion scores."""
        pass
