"""
Shared Kernel - Common domain concepts used across bounded contexts.

The shared kernel contains domain concepts that are shared between multiple
bounded contexts but are not specific to any single context.
"""

from .value_objects import (
    EntityId,
    Timestamp,
    Score,
    Confidence,
    ModelName,
    ProviderName,
    EvaluationId,
    BatchId,
    SessionId,
)

from .domain_events import (
    DomainEvent,
    DomainEventHandler,
    DomainEventPublisher,
    EvaluationCompleted,
    BatchProcessingStarted,
    BatchProcessingCompleted,
    EvaluationFailed,
)

from .exceptions import (
    DomainException,
    InvalidScoreException,
    InvalidModelException,
    InvalidProviderException,
    EvaluationException,
    BatchProcessingException,
)

__all__ = [
    # Value Objects
    "EntityId",
    "Timestamp",
    "Score",
    "Confidence",
    "ModelName",
    "ProviderName",
    "EvaluationId",
    "BatchId",
    "SessionId",
    # Domain Events
    "DomainEvent",
    "DomainEventHandler",
    "DomainEventPublisher",
    "EvaluationCompleted",
    "BatchProcessingStarted",
    "BatchProcessingCompleted",
    "EvaluationFailed",
    # Exceptions
    "DomainException",
    "InvalidScoreException",
    "InvalidModelException",
    "InvalidProviderException",
    "EvaluationException",
    "BatchProcessingException",
]
