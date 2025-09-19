"""
Data persistence domain models and interfaces.

This module provides domain models and interfaces for persisting evaluation results,
managing evaluation history, and implementing caching strategies.
"""

from .models import (
    EvaluationRecord,
    EvaluationHistory,
    CacheEntry,
    EvaluationMetadata,
    PersistenceConfig,
)
from .interfaces import (
    EvaluationRepository,
    CacheRepository,
    HistoryRepository,
    PersistenceService,
)

__all__ = [
    "EvaluationRecord",
    "EvaluationHistory",
    "CacheEntry",
    "EvaluationMetadata",
    "PersistenceConfig",
    "EvaluationRepository",
    "CacheRepository",
    "HistoryRepository",
    "PersistenceService",
]
