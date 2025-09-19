"""
Data persistence interfaces.

Defines abstract interfaces for evaluation result storage, caching,
and history management.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from .models import (
    EvaluationRecord,
    EvaluationHistory,
    CacheEntry,
    PersistenceConfig,
)


class EvaluationRepository(ABC):
    """Repository interface for evaluation records."""

    @abstractmethod
    async def save(self, record: EvaluationRecord) -> None:
        """Save an evaluation record."""
        pass

    @abstractmethod
    async def get_by_id(self, record_id: UUID) -> Optional[EvaluationRecord]:
        """Get evaluation record by ID."""
        pass

    @abstractmethod
    async def get_by_hash(self, record_hash: str) -> Optional[EvaluationRecord]:
        """Get evaluation record by hash."""
        pass

    @abstractmethod
    async def list(
        self,
        page: int = 1,
        page_size: int = 50,
        tags: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        model: Optional[str] = None,
        judge_model: Optional[str] = None,
    ) -> EvaluationHistory:
        """List evaluation records with filtering."""
        pass

    @abstractmethod
    async def update_metadata(
        self, record_id: UUID, metadata_updates: Dict[str, Any]
    ) -> Optional[EvaluationRecord]:
        """Update record metadata."""
        pass

    @abstractmethod
    async def delete(self, record_id: UUID) -> bool:
        """Delete evaluation record."""
        pass

    @abstractmethod
    async def count(self) -> int:
        """Get total number of records."""
        pass

    @abstractmethod
    async def get_statistics(self) -> Dict[str, Any]:
        """Get evaluation statistics."""
        pass


class CacheRepository(ABC):
    """Repository interface for cache management."""

    @abstractmethod
    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get cache entry by key."""
        pass

    @abstractmethod
    async def set(
        self, key: str, record: EvaluationRecord, ttl_hours: Optional[int] = None
    ) -> None:
        """Set cache entry."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete cache entry."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""
        pass

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Clean up expired cache entries."""
        pass

    @abstractmethod
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        pass

    @abstractmethod
    async def generate_key(
        self, prompt: str, response: str, criteria_hash: str, judge_model: str
    ) -> str:
        """Generate cache key for evaluation."""
        pass


class HistoryRepository(ABC):
    """Repository interface for evaluation history management."""

    @abstractmethod
    async def get_history(
        self,
        page: int = 1,
        page_size: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> EvaluationHistory:
        """Get evaluation history with filtering."""
        pass

    @abstractmethod
    async def search(
        self, query: str, page: int = 1, page_size: int = 50
    ) -> EvaluationHistory:
        """Search evaluation records."""
        pass

    @abstractmethod
    async def get_by_session(self, session_id: str) -> List[EvaluationRecord]:
        """Get records by session ID."""
        pass

    @abstractmethod
    async def get_by_batch(self, batch_id: str) -> List[EvaluationRecord]:
        """Get records by batch ID."""
        pass

    @abstractmethod
    async def export(
        self,
        format: str = "json",
        filters: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """Export evaluation history."""
        pass

    @abstractmethod
    async def import_data(self, data_path: str, format: str = "json") -> int:
        """Import evaluation data."""
        pass


class PersistenceService(ABC):
    """Service interface for data persistence operations."""

    @abstractmethod
    async def save_evaluation(
        self,
        candidate: "CandidateResponse",
        result: "Union[MultiCriteriaEvaluationResult, EvaluationResult]",
        criteria_hash: str,
        judge_model: str,
        provider: str,
        evaluation_time_ms: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EvaluationRecord:
        """Save evaluation result with automatic caching."""
        pass

    @abstractmethod
    async def get_evaluation(
        self,
        prompt: str,
        response: str,
        criteria_hash: str,
        judge_model: str,
    ) -> Optional[EvaluationRecord]:
        """Get evaluation result (from cache or storage)."""
        pass

    @abstractmethod
    async def list_evaluations(
        self,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ) -> EvaluationHistory:
        """List evaluation records with filtering."""
        pass

    @abstractmethod
    async def search_evaluations(
        self, query: str, page: int = 1, page_size: int = 50
    ) -> EvaluationHistory:
        """Search evaluation records."""
        pass

    @abstractmethod
    async def update_evaluation_metadata(
        self, record_id: UUID, metadata_updates: Dict[str, Any]
    ) -> Optional[EvaluationRecord]:
        """Update evaluation metadata."""
        pass

    @abstractmethod
    async def delete_evaluation(self, record_id: UUID) -> bool:
        """Delete evaluation record."""
        pass

    @abstractmethod
    async def export_evaluations(
        self,
        format: str = "json",
        filters: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """Export evaluation data."""
        pass

    @abstractmethod
    async def import_evaluations(self, data_path: str, format: str = "json") -> int:
        """Import evaluation data."""
        pass

    @abstractmethod
    async def get_statistics(self) -> Dict[str, Any]:
        """Get evaluation statistics."""
        pass

    @abstractmethod
    async def cleanup_cache(self) -> int:
        """Clean up expired cache entries."""
        pass

    @abstractmethod
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        pass
