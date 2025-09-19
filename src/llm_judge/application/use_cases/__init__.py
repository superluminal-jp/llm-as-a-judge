"""
Use Cases for the Application Layer.

Use cases represent the application's business logic and orchestrate
between the domain layer and infrastructure layer.
"""

from .evaluation_use_cases import (
    EvaluateResponseUseCase,
    CompareResponsesUseCase,
    MultiCriteriaEvaluationUseCase,
)

from .batch_use_cases import (
    ProcessBatchUseCase,
    CreateBatchUseCase,
    MonitorBatchUseCase,
    CancelBatchUseCase,
)

from .criteria_use_cases import (
    CreateCriteriaUseCase,
    UpdateCriteriaUseCase,
    DeleteCriteriaUseCase,
    ListCriteriaUseCase,
)

from .persistence_use_cases import (
    SaveEvaluationUseCase,
    RetrieveEvaluationUseCase,
    ListEvaluationsUseCase,
    SearchEvaluationsUseCase,
)

__all__ = [
    # Evaluation Use Cases
    "EvaluateResponseUseCase",
    "CompareResponsesUseCase",
    "MultiCriteriaEvaluationUseCase",
    # Batch Use Cases
    "ProcessBatchUseCase",
    "CreateBatchUseCase",
    "MonitorBatchUseCase",
    "CancelBatchUseCase",
    # Criteria Use Cases
    "CreateCriteriaUseCase",
    "UpdateCriteriaUseCase",
    "DeleteCriteriaUseCase",
    "ListCriteriaUseCase",
    # Persistence Use Cases
    "SaveEvaluationUseCase",
    "RetrieveEvaluationUseCase",
    "ListEvaluationsUseCase",
    "SearchEvaluationsUseCase",
]
