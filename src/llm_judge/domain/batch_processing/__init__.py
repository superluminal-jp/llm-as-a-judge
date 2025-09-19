"""
Batch Processing Bounded Context.

This bounded context contains all domain logic related to processing
multiple evaluations in batches with proper orchestration and monitoring.
"""

from .entities import (
    BatchRequest,
    BatchResult,
    BatchEvaluationItem,
    BatchProgress,
)

from .value_objects import (
    BatchStatus,
    EvaluationType,
    BatchConfiguration,
    ProcessingMetrics,
)

from .services import (
    BatchProcessingService,
    BatchOrchestrationService,
    BatchMonitoringService,
)

from .repositories import (
    BatchRepository,
    BatchProgressRepository,
)

from .specifications import (
    BatchValidationSpecification,
    BatchProcessingSpecification,
    BatchCompletionSpecification,
)

__all__ = [
    # Entities
    "BatchRequest",
    "BatchResult",
    "BatchEvaluationItem",
    "BatchProgress",
    # Value Objects
    "BatchStatus",
    "EvaluationType",
    "BatchConfiguration",
    "ProcessingMetrics",
    # Services
    "BatchProcessingService",
    "BatchOrchestrationService",
    "BatchMonitoringService",
    # Repositories
    "BatchRepository",
    "BatchProgressRepository",
    # Specifications
    "BatchValidationSpecification",
    "BatchProcessingSpecification",
    "BatchCompletionSpecification",
]
