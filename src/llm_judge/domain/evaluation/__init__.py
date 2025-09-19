"""
Evaluation Bounded Context.

This bounded context contains all domain logic related to evaluating
LLM responses using various criteria and scoring systems.
"""

from .entities import (
    Evaluation,
    EvaluationCriteria,
    CriterionDefinition,
    CriterionScore,
    AggregatedScore,
    MultiCriteriaResult,
)

from .value_objects import (
    EvaluationType,
    EvaluationStatus,
    EvaluationMetadata,
)

from .services import (
    EvaluationService,
    CriteriaService,
    ScoringService,
    MultiCriteriaEvaluationService,
)

from .repositories import (
    EvaluationRepository,
    CriteriaRepository,
)

from .specifications import (
    EvaluationSpecification,
    CriteriaSpecification,
    ScoringSpecification,
)

__all__ = [
    # Entities
    "Evaluation",
    "EvaluationCriteria",
    "CriterionDefinition",
    "CriterionScore",
    "AggregatedScore",
    "MultiCriteriaResult",
    # Value Objects
    "EvaluationType",
    "EvaluationStatus",
    "EvaluationMetadata",
    # Services
    "EvaluationService",
    "CriteriaService",
    "ScoringService",
    "MultiCriteriaEvaluationService",
    # Repositories
    "EvaluationRepository",
    "CriteriaRepository",
    # Specifications
    "EvaluationSpecification",
    "CriteriaSpecification",
    "ScoringSpecification",
]
