"""
Persistence service implementation.

Provides high-level service for managing evaluation data persistence,
caching, and history operations.
"""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

# CandidateResponse will be imported where needed to avoid circular imports
from ...domain.evaluation.results import (
    MultiCriteriaResult,
)
from ...domain.persistence.interfaces import PersistenceService
from ...domain.persistence.models import (
    EvaluationRecord,
    EvaluationHistory,
    EvaluationMetadata,
    PersistenceConfig,
)
from .json_repository import (
    JsonEvaluationRepository,
    JsonCacheRepository,
    JsonHistoryRepository,
)


class PersistenceServiceImpl(PersistenceService):
    """Implementation of persistence service."""

    def __init__(self, config: PersistenceConfig):
        self.config = config
        self.evaluation_repo = JsonEvaluationRepository(config.storage_path)
        self.cache_repo = JsonCacheRepository(
            config.storage_path, config.max_cache_size
        )
        self.history_repo = JsonHistoryRepository(config.storage_path)

    async def save_evaluation(
        self,
        candidate: Any,  # CandidateResponse - imported where needed to avoid circular imports
        result: MultiCriteriaResult,
        criteria_hash: str,
        judge_model: str,
        provider: str,
        evaluation_time_ms: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EvaluationRecord:
        """Save evaluation result with automatic caching."""
        # Create evaluation metadata
        eval_metadata = EvaluationMetadata(
            tags=metadata.get("tags", []) if metadata else [],
            notes=metadata.get("notes") if metadata else None,
            user_id=metadata.get("user_id") if metadata else None,
            session_id=metadata.get("session_id") if metadata else None,
            batch_id=metadata.get("batch_id") if metadata else None,
        )

        # Create evaluation record
        record = EvaluationRecord(
            id=str(eval_metadata.id),
            candidate=candidate,
            result=result,
            criteria_hash=criteria_hash,
            judge_model=judge_model,
            provider=provider,
            evaluation_time_ms=evaluation_time_ms,
            evaluated_at=eval_metadata.created_at,
            metadata=eval_metadata,
        )

        # Save to storage
        await self.evaluation_repo.save(record)

        # Cache if enabled
        if self.config.cache_enabled:
            cache_key = await self.cache_repo.generate_key(
                candidate.prompt,
                candidate.response,
                criteria_hash,
                judge_model,
            )
            await self.cache_repo.set(cache_key, record, self.config.cache_ttl_hours)

        return record

    async def get_evaluation(
        self,
        prompt: str,
        response: str,
        criteria_hash: str,
        judge_model: str,
    ) -> Optional[
        Any
    ]:  # EvaluationRecord - imported where needed to avoid circular imports
        """Get evaluation result (from cache or storage)."""
        # Try cache first if enabled
        if self.config.cache_enabled:
            cache_key = await self.cache_repo.generate_key(
                prompt, response, criteria_hash, judge_model
            )
            cached_entry = await self.cache_repo.get(cache_key)
            if cached_entry:
                return cached_entry.record

        # Fall back to storage
        record_hash = self._generate_record_hash(
            prompt, response, criteria_hash, judge_model
        )
        return await self.evaluation_repo.get_by_hash(record_hash)

    async def list_evaluations(
        self,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ) -> Any:  # EvaluationHistory - imported where needed to avoid circular imports
        """List evaluation records with filtering."""
        return await self.evaluation_repo.list(
            page=page,
            page_size=page_size,
            tags=filters.get("tags"),
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
            model=filters.get("model"),
            judge_model=filters.get("judge_model"),
        )

    async def search_evaluations(
        self, query: str, page: int = 1, page_size: int = 50
    ) -> EvaluationHistory:
        """Search evaluation records."""
        return await self.history_repo.search(query, page, page_size)

    async def update_evaluation_metadata(
        self, record_id: UUID, metadata_updates: Dict[str, Any]
    ) -> Optional[EvaluationRecord]:
        """Update evaluation metadata."""
        return await self.evaluation_repo.update_metadata(record_id, metadata_updates)

    async def delete_evaluation(self, record_id: UUID) -> bool:
        """Delete evaluation record."""
        # Get record to find cache key
        record = await self.evaluation_repo.get_by_id(record_id)
        if not record:
            return False

        # Remove from cache if exists
        if self.config.cache_enabled:
            cache_key = await self.cache_repo.generate_key(
                record.candidate.prompt,
                record.candidate.response,
                record.criteria_hash,
                record.judge_model,
            )
            await self.cache_repo.delete(cache_key)

        # Remove from storage
        return await self.evaluation_repo.delete(record_id)

    async def export_evaluations(
        self,
        format: str = "json",
        filters: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """Export evaluation data."""
        return await self.history_repo.export(format, filters, output_path)

    async def import_evaluations(self, data_path: str, format: str = "json") -> int:
        """Import evaluation data."""
        return await self.history_repo.import_data(data_path, format)

    async def get_statistics(self) -> Dict[str, Any]:
        """Get evaluation statistics."""
        return await self.evaluation_repo.get_statistics()

    async def cleanup_cache(self) -> int:
        """Clean up expired cache entries."""
        return await self.cache_repo.cleanup_expired()

    async def clear_cache(self) -> None:
        """Clear all cache entries."""
        await self.cache_repo.clear()

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return await self.cache_repo.get_cache_stats()

    def _generate_record_hash(
        self, prompt: str, response: str, criteria_hash: str, judge_model: str
    ) -> str:
        """Generate hash for evaluation record."""
        content = f"{prompt}|{response}|{criteria_hash}|{judge_model}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def get_evaluation_by_id(self, record_id: UUID) -> Optional[EvaluationRecord]:
        """Get evaluation record by ID."""
        return await self.evaluation_repo.get_by_id(record_id)

    async def get_evaluations_by_session(
        self, session_id: str
    ) -> List[EvaluationRecord]:
        """Get evaluations by session ID."""
        return await self.history_repo.get_by_session(session_id)

    async def get_evaluations_by_batch(self, batch_id: str) -> List[EvaluationRecord]:
        """Get evaluations by batch ID."""
        return await self.history_repo.get_by_batch(batch_id)

    async def get_evaluations_by_tags(self, tags: List[str]) -> List[EvaluationRecord]:
        """Get evaluations by tags."""
        history = await self.list_evaluations(tags=tags, page_size=1000)
        return history.records

    async def get_evaluations_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> List[EvaluationRecord]:
        """Get evaluations by date range."""
        history = await self.list_evaluations(
            start_date=start_date,
            end_date=end_date,
            page_size=1000,
        )
        return history.records

    async def get_evaluations_by_model(self, model: str) -> List[EvaluationRecord]:
        """Get evaluations by model."""
        history = await self.list_evaluations(model=model, page_size=1000)
        return history.records

    async def get_evaluations_by_judge_model(
        self, judge_model: str
    ) -> List[EvaluationRecord]:
        """Get evaluations by judge model."""
        history = await self.list_evaluations(judge_model=judge_model, page_size=1000)
        return history.records

    async def add_tags_to_evaluation(
        self, record_id: UUID, tags: List[str]
    ) -> Optional[EvaluationRecord]:
        """Add tags to evaluation record."""
        record = await self.evaluation_repo.get_by_id(record_id)
        if not record:
            return None

        # Merge with existing tags
        existing_tags = record.metadata.tags
        new_tags = list(set(existing_tags + tags))

        return await self.update_evaluation_metadata(record_id, {"tags": new_tags})

    async def remove_tags_from_evaluation(
        self, record_id: UUID, tags: List[str]
    ) -> Optional[EvaluationRecord]:
        """Remove tags from evaluation record."""
        record = await self.evaluation_repo.get_by_id(record_id)
        if not record:
            return None

        # Remove specified tags
        existing_tags = record.metadata.tags
        new_tags = [tag for tag in existing_tags if tag not in tags]

        return await self.update_evaluation_metadata(record_id, {"tags": new_tags})

    async def update_evaluation_notes(
        self, record_id: UUID, notes: str
    ) -> Optional[EvaluationRecord]:
        """Update evaluation notes."""
        return await self.update_evaluation_metadata(record_id, {"notes": notes})

    async def clear_all_data(self) -> None:
        """Clear all evaluation data (use with caution)."""
        # Clear cache
        if self.config.cache_enabled:
            await self.cache_repo.clear()

        # Clear storage (this would need to be implemented in the repository)
        # For now, we'll just clear the cache
        pass

    async def get_storage_info(self) -> Dict[str, Any]:
        """Get storage information."""
        stats = await self.get_statistics()
        cache_stats = await self.get_cache_stats()

        return {
            "storage_path": self.config.storage_path,
            "storage_format": self.config.storage_format.value,
            "cache_enabled": self.config.cache_enabled,
            "evaluation_stats": stats,
            "cache_stats": cache_stats,
            "config": self.config.to_dict(),
        }
