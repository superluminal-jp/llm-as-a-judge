"""
Domain layer for LLM-as-a-Judge system.

Contains business logic and domain models following Domain-Driven Design principles.
The domain layer has no dependencies on external frameworks or infrastructure.
"""

from .batch import (
    BatchRequest, 
    BatchResult, 
    BatchStatus, 
    BatchEvaluationItem, 
    BatchProgress,
    EvaluationType,
    BatchEvaluationService
)

__all__ = [
    "BatchRequest",
    "BatchResult", 
    "BatchStatus", 
    "BatchEvaluationItem", 
    "BatchProgress",
    "EvaluationType",
    "BatchEvaluationService"
]