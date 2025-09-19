"""
JSON-based persistence implementations.

Provides file-based storage using JSON format for evaluation records,
caching, and history management.
"""

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from ...domain.persistence.interfaces import (
    EvaluationRepository,
    CacheRepository,
    HistoryRepository,
)
from ...domain.persistence.models import (
    EvaluationRecord,
    EvaluationHistory,
    CacheEntry,
)


class JsonEvaluationRepository(EvaluationRepository):
    """JSON-based evaluation repository."""

    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.records_file = self.storage_path / "evaluations.json"
        self.index_file = self.storage_path / "evaluations_index.json"
        self._ensure_storage_path()
        self._load_index()

    def _ensure_storage_path(self):
        """Ensure storage directory exists."""
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _load_index(self):
        """Load evaluation index."""
        if self.index_file.exists():
            with open(self.index_file, "r", encoding="utf-8") as f:
                self.index = json.load(f)
        else:
            self.index = {
                "by_id": {},
                "by_hash": {},
                "by_date": {},
                "by_model": {},
                "by_judge_model": {},
                "by_tags": {},
                "total_count": 0,
            }

    def _save_index(self):
        """Save evaluation index."""
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self.index, f, indent=2, ensure_ascii=False)

    def _load_records(self) -> List[Dict[str, Any]]:
        """Load all evaluation records."""
        if not self.records_file.exists():
            return []

        with open(self.records_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_records(self, records: List[Dict[str, Any]]):
        """Save all evaluation records."""
        with open(self.records_file, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

    def _update_index(self, record: EvaluationRecord, operation: str = "add"):
        """Update search index."""
        record_id = str(record.metadata.id)
        record_hash = record.get_hash()

        if operation == "add":
            self.index["by_id"][record_id] = record_hash
            self.index["by_hash"][record_hash] = record_id

            # Date index
            date_key = record.metadata.created_at.date().isoformat()
            if date_key not in self.index["by_date"]:
                self.index["by_date"][date_key] = []
            self.index["by_date"][date_key].append(record_id)

            # Model index
            if record.candidate.model not in self.index["by_model"]:
                self.index["by_model"][record.candidate.model] = []
            self.index["by_model"][record.candidate.model].append(record_id)

            # Judge model index
            if record.judge_model not in self.index["by_judge_model"]:
                self.index["by_judge_model"][record.judge_model] = []
            self.index["by_judge_model"][record.judge_model].append(record_id)

            # Tags index
            for tag in record.metadata.tags:
                if tag not in self.index["by_tags"]:
                    self.index["by_tags"][tag] = []
                self.index["by_tags"][tag].append(record_id)

            self.index["total_count"] += 1

        elif operation == "remove":
            if record_id in self.index["by_id"]:
                del self.index["by_id"][record_id]
            if record_hash in self.index["by_hash"]:
                del self.index["by_hash"][record_hash]

            # Remove from other indexes
            for index_name in ["by_date", "by_model", "by_judge_model", "by_tags"]:
                for key, record_ids in self.index[index_name].items():
                    if record_id in record_ids:
                        record_ids.remove(record_id)
                        if not record_ids:
                            del self.index[index_name][key]

            self.index["total_count"] = max(0, self.index["total_count"] - 1)

    async def save(self, record: EvaluationRecord) -> None:
        """Save an evaluation record."""
        records = self._load_records()

        # Check if record already exists
        record_id = str(record.metadata.id)
        existing_index = next(
            (i for i, r in enumerate(records) if r["metadata"]["id"] == record_id), None
        )

        record_dict = record.to_dict()

        if existing_index is not None:
            # Update existing record
            records[existing_index] = record_dict
        else:
            # Add new record
            records.append(record_dict)
            self._update_index(record, "add")

        self._save_records(records)
        self._save_index()

    async def get_by_id(self, record_id: UUID) -> Optional[EvaluationRecord]:
        """Get evaluation record by ID."""
        records = self._load_records()
        record_id_str = str(record_id)

        for record_dict in records:
            if record_dict["metadata"]["id"] == record_id_str:
                return EvaluationRecord.from_dict(record_dict)

        return None

    async def get_by_hash(self, record_hash: str) -> Optional[EvaluationRecord]:
        """Get evaluation record by hash."""
        if record_hash not in self.index["by_hash"]:
            return None

        record_id = self.index["by_hash"][record_hash]
        return await self.get_by_id(UUID(record_id))

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
        records = self._load_records()
        filtered_records = []

        for record_dict in records:
            record = EvaluationRecord.from_dict(record_dict)

            # Apply filters
            if tags and not any(tag in record.metadata.tags for tag in tags):
                continue

            if start_date and record.metadata.created_at < start_date:
                continue

            if end_date and record.metadata.created_at > end_date:
                continue

            if model and record.candidate.model != model:
                continue

            if judge_model and record.judge_model != judge_model:
                continue

            filtered_records.append(record)

        # Sort by creation date (newest first)
        filtered_records.sort(key=lambda r: r.metadata.created_at, reverse=True)

        # Pagination
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        page_records = filtered_records[start_index:end_index]

        return EvaluationHistory(
            records=page_records,
            total_count=len(filtered_records),
            page=page,
            page_size=page_size,
        )

    async def update_metadata(
        self, record_id: UUID, metadata_updates: Dict[str, Any]
    ) -> Optional[EvaluationRecord]:
        """Update record metadata."""
        record = await self.get_by_id(record_id)
        if not record:
            return None

        # Create updated metadata
        updated_metadata = record.metadata
        metadata_dict = updated_metadata.to_dict()
        metadata_dict.update(metadata_updates)
        metadata_dict["updated_at"] = datetime.now(timezone.utc).isoformat()

        updated_metadata = updated_metadata.__class__.from_dict(metadata_dict)

        # Create updated record
        updated_record = EvaluationRecord(
            metadata=updated_metadata,
            candidate=record.candidate,
            result=record.result,
            criteria_hash=record.criteria_hash,
            judge_model=record.judge_model,
            provider=record.provider,
            evaluation_time_ms=record.evaluation_time_ms,
        )

        await self.save(updated_record)
        return updated_record

    async def delete(self, record_id: UUID) -> bool:
        """Delete evaluation record."""
        record = await self.get_by_id(record_id)
        if not record:
            return False

        records = self._load_records()
        record_id_str = str(record_id)

        # Remove from records
        records = [r for r in records if r["metadata"]["id"] != record_id_str]

        # Update index
        self._update_index(record, "remove")

        self._save_records(records)
        self._save_index()
        return True

    async def count(self) -> int:
        """Get total number of records."""
        return self.index["total_count"]

    async def get_statistics(self) -> Dict[str, Any]:
        """Get evaluation statistics."""
        records = self._load_records()
        if not records:
            return {"total_evaluations": 0}

        # Calculate statistics
        total_evaluations = len(records)

        # Model distribution
        model_counts = {}
        judge_model_counts = {}
        provider_counts = {}

        for record_dict in records:
            record = EvaluationRecord.from_dict(record_dict)
            model_counts[record.candidate.model] = (
                model_counts.get(record.candidate.model, 0) + 1
            )
            judge_model_counts[record.judge_model] = (
                judge_model_counts.get(record.judge_model, 0) + 1
            )
            provider_counts[record.provider] = (
                provider_counts.get(record.provider, 0) + 1
            )

        # Score statistics
        scores = []
        for record_dict in records:
            record = EvaluationRecord.from_dict(record_dict)
            if hasattr(record.result, "aggregated"):
                scores.append(record.result.aggregated.overall_score)
            else:
                scores.append(record.result.score)

        avg_score = sum(scores) / len(scores) if scores else 0
        min_score = min(scores) if scores else 0
        max_score = max(scores) if scores else 0

        return {
            "total_evaluations": total_evaluations,
            "average_score": round(avg_score, 2),
            "min_score": min_score,
            "max_score": max_score,
            "model_distribution": model_counts,
            "judge_model_distribution": judge_model_counts,
            "provider_distribution": provider_counts,
        }


class JsonCacheRepository(CacheRepository):
    """JSON-based cache repository."""

    def __init__(self, storage_path: str, max_size: int = 1000):
        self.storage_path = Path(storage_path)
        self.cache_file = self.storage_path / "cache.json"
        self.max_size = max_size
        self._ensure_storage_path()

    def _ensure_storage_path(self):
        """Ensure storage directory exists."""
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        """Load cache entries."""
        if not self.cache_file.exists():
            return {}

        with open(self.cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_cache(self, cache: Dict[str, Dict[str, Any]]):
        """Save cache entries."""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)

    def _evict_oldest(self, cache: Dict[str, Dict[str, Any]]):
        """Evict oldest cache entries if over limit."""
        if len(cache) <= self.max_size:
            return

        # Sort by last_accessed and remove oldest
        sorted_entries = sorted(cache.items(), key=lambda x: x[1]["last_accessed"])

        entries_to_remove = len(cache) - self.max_size
        for key, _ in sorted_entries[:entries_to_remove]:
            del cache[key]

    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get cache entry by key."""
        cache = self._load_cache()

        if key not in cache:
            return None

        entry_dict = cache[key]
        entry = CacheEntry.from_dict(entry_dict)

        # Check if expired
        if entry.is_expired():
            del cache[key]
            self._save_cache(cache)
            return None

        # Touch entry (update access info)
        touched_entry = entry.touch()
        cache[key] = touched_entry.to_dict()
        self._save_cache(cache)

        return touched_entry

    async def set(
        self, key: str, record: EvaluationRecord, ttl_hours: Optional[int] = None
    ) -> None:
        """Set cache entry."""
        cache = self._load_cache()

        expires_at = None
        if ttl_hours:
            expires_at = datetime.now(timezone.utc).replace(
                hour=datetime.now(timezone.utc).hour + ttl_hours
            )

        entry = CacheEntry(
            key=key,
            record=record,
            expires_at=expires_at,
        )

        cache[key] = entry.to_dict()

        # Evict oldest entries if over limit
        self._evict_oldest(cache)

        self._save_cache(cache)

    async def delete(self, key: str) -> bool:
        """Delete cache entry."""
        cache = self._load_cache()

        if key not in cache:
            return False

        del cache[key]
        self._save_cache(cache)
        return True

    async def clear(self) -> None:
        """Clear all cache entries."""
        self._save_cache({})

    async def cleanup_expired(self) -> int:
        """Clean up expired cache entries."""
        cache = self._load_cache()
        expired_keys = []

        for key, entry_dict in cache.items():
            entry = CacheEntry.from_dict(entry_dict)
            if entry.is_expired():
                expired_keys.append(key)

        for key in expired_keys:
            del cache[key]

        if expired_keys:
            self._save_cache(cache)

        return len(expired_keys)

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        cache = self._load_cache()

        if not cache:
            return {
                "total_entries": 0,
                "expired_entries": 0,
                "total_access_count": 0,
                "average_access_count": 0,
            }

        total_access_count = 0
        expired_count = 0

        for entry_dict in cache.values():
            entry = CacheEntry.from_dict(entry_dict)
            total_access_count += entry.access_count
            if entry.is_expired():
                expired_count += 1

        return {
            "total_entries": len(cache),
            "expired_entries": expired_count,
            "total_access_count": total_access_count,
            "average_access_count": total_access_count / len(cache) if cache else 0,
            "max_size": self.max_size,
            "utilization": len(cache) / self.max_size,
        }

    async def generate_key(
        self, prompt: str, response: str, criteria_hash: str, judge_model: str
    ) -> str:
        """Generate cache key for evaluation."""
        import hashlib

        content = f"{prompt}|{response}|{criteria_hash}|{judge_model}"
        return hashlib.sha256(content.encode()).hexdigest()


class JsonHistoryRepository(HistoryRepository):
    """JSON-based history repository."""

    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.evaluation_repo = JsonEvaluationRepository(storage_path)

    async def get_history(
        self,
        page: int = 1,
        page_size: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> EvaluationHistory:
        """Get evaluation history with filtering."""
        if not filters:
            filters = {}

        return await self.evaluation_repo.list(
            page=page,
            page_size=page_size,
            tags=filters.get("tags"),
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
            model=filters.get("model"),
            judge_model=filters.get("judge_model"),
        )

    async def search(
        self, query: str, page: int = 1, page_size: int = 50
    ) -> EvaluationHistory:
        """Search evaluation records."""
        # Simple text search implementation
        records = self.evaluation_repo._load_records()
        matching_records = []

        query_lower = query.lower()

        for record_dict in records:
            record = EvaluationRecord.from_dict(record_dict)

            # Search in prompt, response, and reasoning
            searchable_text = (
                record.candidate.prompt.lower() + record.candidate.response.lower()
            )

            if hasattr(record.result, "aggregated"):
                searchable_text += record.result.aggregated.reasoning.lower()
            else:
                searchable_text += record.result.reasoning.lower()

            if query_lower in searchable_text:
                matching_records.append(record)

        # Sort by creation date (newest first)
        matching_records.sort(key=lambda r: r.metadata.created_at, reverse=True)

        # Pagination
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        page_records = matching_records[start_index:end_index]

        return EvaluationHistory(
            records=page_records,
            total_count=len(matching_records),
            page=page,
            page_size=page_size,
        )

    async def get_by_session(self, session_id: str) -> List[EvaluationRecord]:
        """Get records by session ID."""
        history = await self.get_history(filters={"session_id": session_id})
        return history.records

    async def get_by_batch(self, batch_id: str) -> List[EvaluationRecord]:
        """Get records by batch ID."""
        history = await self.get_history(filters={"batch_id": batch_id})
        return history.records

    async def export(
        self,
        format: str = "json",
        filters: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """Export evaluation history."""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.storage_path / f"export_{timestamp}.{format}"

        history = await self.get_history(filters=filters)

        if format == "json":
            export_data = {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "total_records": history.total_count,
                "records": [record.to_dict() for record in history.records],
            }

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

        return str(output_path)

    async def import_data(self, data_path: str, format: str = "json") -> int:
        """Import evaluation data."""
        imported_count = 0

        if format == "json":
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "records" in data:
                for record_dict in data["records"]:
                    record = EvaluationRecord.from_dict(record_dict)
                    await self.evaluation_repo.save(record)
                    imported_count += 1

        return imported_count
