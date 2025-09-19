"""
Data persistence domain models.

Defines domain models for storing and managing evaluation results,
caching, and evaluation history.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from ..evaluation.results import MultiCriteriaResult

# CandidateResponse will be imported where needed to avoid circular imports


class StorageFormat(Enum):
    """Supported storage formats for evaluation data."""

    JSON = "json"
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


class CacheStrategy(Enum):
    """Cache invalidation strategies."""

    TIME_BASED = "time_based"  # Expire after time
    VERSION_BASED = "version_based"  # Expire when criteria version changes
    MANUAL = "manual"  # Manual invalidation only


@dataclass(frozen=True)
class EvaluationMetadata:
    """Metadata for evaluation records."""

    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    batch_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "tags": self.tags,
            "notes": self.notes,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "batch_id": self.batch_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationMetadata":
        """Create from dictionary."""
        return cls(
            id=UUID(data["id"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            version=data["version"],
            tags=data.get("tags", []),
            notes=data.get("notes"),
            user_id=data.get("user_id"),
            session_id=data.get("session_id"),
            batch_id=data.get("batch_id"),
        )


@dataclass
class EvaluationRecord:
    """Complete evaluation record with metadata."""

    id: str
    candidate: (
        Any  # CandidateResponse - imported where needed to avoid circular imports
    )
    result: MultiCriteriaResult
    criteria_hash: str
    judge_model: str
    provider: str
    evaluation_time_ms: int
    evaluated_at: datetime
    metadata: Optional[EvaluationMetadata] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "candidate": {
                "prompt": self.candidate.prompt,
                "response": self.candidate.response,
            },
            "result": self._serialize_result(),
            "criteria_hash": self.criteria_hash,
            "judge_model": self.judge_model,
            "provider": self.provider,
            "evaluation_time_ms": self.evaluation_time_ms,
            "evaluated_at": self.evaluated_at.isoformat(),
        }

    def _serialize_result(self) -> Dict[str, Any]:
        """Serialize evaluation result."""
        return {
            "criterion_scores": {
                name: {
                    "score": score.score,
                    "reasoning": score.reasoning,
                }
                for name, score in self.result.criterion_scores.items()
            },
            "aggregated": {
                "overall_score": self.result.aggregated.overall_score,
            },
        }

    @classmethod
    def _deserialize_result(cls, data: Dict[str, Any]) -> MultiCriteriaResult:
        """Deserialize evaluation result from dictionary."""
        from ..evaluation.results import (
            MultiCriteriaResult,
            AggregatedScore,
            CriterionScore,
        )

        criterion_scores = {
            name: CriterionScore(
                criterion_name=name,
                score=score_data["score"],
                reasoning=score_data["reasoning"],
            )
            for name, score_data in data["criterion_scores"].items()
        }

        aggregated = AggregatedScore(
            overall_score=data["aggregated"]["overall_score"],
            weighted_score=data["aggregated"].get(
                "weighted_score", data["aggregated"]["overall_score"]
            ),
            confidence=data["aggregated"].get("confidence", 0.8),
            min_score=data["aggregated"].get("min_score", 1),
            max_score=data["aggregated"].get("max_score", 5),
        )

        return MultiCriteriaResult(
            criterion_scores=criterion_scores,
            aggregated=aggregated,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationRecord":
        """Create from dictionary."""
        from ...application.services.llm_judge_service import CandidateResponse

        candidate = CandidateResponse(
            prompt=data["candidate"]["prompt"],
            response=data["candidate"]["response"],
        )

        result = cls._deserialize_result(data["result"])

        return cls(
            id=data["id"],
            candidate=candidate,
            result=result,
            criteria_hash=data["criteria_hash"],
            judge_model=data["judge_model"],
            provider=data["provider"],
            evaluation_time_ms=data["evaluation_time_ms"],
            evaluated_at=datetime.fromisoformat(data["evaluated_at"]),
        )

    def get_hash(self) -> str:
        """Get unique hash for this evaluation record."""
        content = f"{self.candidate.prompt}|{self.candidate.response}|{self.criteria_hash}|{self.judge_model}"
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass(frozen=True)
class CacheEntry:
    """Cache entry for evaluation results."""

    key: str
    record: EvaluationRecord
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def touch(self) -> "CacheEntry":
        """Update access information."""
        return CacheEntry(
            key=self.key,
            record=self.record,
            created_at=self.created_at,
            expires_at=self.expires_at,
            access_count=self.access_count + 1,
            last_accessed=datetime.now(timezone.utc),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "key": self.key,
            "record": self.record.to_dict(),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Create from dictionary."""
        return cls(
            key=data["key"],
            record=EvaluationRecord.from_dict(data["record"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data["expires_at"]
                else None
            ),
            access_count=data["access_count"],
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
        )


@dataclass(frozen=True)
class EvaluationHistory:
    """Collection of evaluation records with query capabilities."""

    records: List[EvaluationRecord]
    total_count: int
    page: int = 1
    page_size: int = 50

    def get_by_id(self, record_id: UUID) -> Optional[EvaluationRecord]:
        """Get record by ID."""
        return next((r for r in self.records if r.metadata.id == record_id), None)

    def get_by_tags(self, tags: List[str]) -> List[EvaluationRecord]:
        """Get records by tags."""
        return [r for r in self.records if any(tag in r.metadata.tags for tag in tags)]

    def get_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> List[EvaluationRecord]:
        """Get records by date range."""
        return [
            r for r in self.records if start_date <= r.metadata.created_at <= end_date
        ]

    def get_by_model(self, model: str) -> List[EvaluationRecord]:
        """Get records by model."""
        return [r for r in self.records if r.candidate.model == model]

    def get_by_judge_model(self, judge_model: str) -> List[EvaluationRecord]:
        """Get records by judge model."""
        return [r for r in self.records if r.judge_model == judge_model]

    def get_statistics(self) -> Dict[str, Any]:
        """Get evaluation statistics."""
        if not self.records:
            return {"total_evaluations": 0}

        # Calculate statistics
        total_evaluations = len(self.records)

        # Model distribution
        model_counts = {}
        judge_model_counts = {}
        provider_counts = {}

        for record in self.records:
            model_counts[record.candidate.model] = (
                model_counts.get(record.candidate.model, 0) + 1
            )
            judge_model_counts[record.judge_model] = (
                judge_model_counts.get(record.judge_model, 0) + 1
            )
            provider_counts[record.provider] = (
                provider_counts.get(record.provider, 0) + 1
            )

        # Score statistics (for multi-criteria results)
        scores = []
        for record in self.records:
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
            "date_range": {
                "earliest": min(
                    r.metadata.created_at for r in self.records
                ).isoformat(),
                "latest": max(r.metadata.created_at for r in self.records).isoformat(),
            },
        }


@dataclass(frozen=True)
class PersistenceConfig:
    """Configuration for data persistence."""

    storage_format: StorageFormat = StorageFormat.JSON
    storage_path: str = "./data"
    cache_enabled: bool = True
    cache_strategy: CacheStrategy = CacheStrategy.TIME_BASED
    cache_ttl_hours: int = 24
    max_cache_size: int = 1000
    auto_cleanup: bool = True
    cleanup_interval_hours: int = 24
    compression_enabled: bool = False
    encryption_enabled: bool = False
    encryption_key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "storage_format": self.storage_format.value,
            "storage_path": self.storage_path,
            "cache_enabled": self.cache_enabled,
            "cache_strategy": self.cache_strategy.value,
            "cache_ttl_hours": self.cache_ttl_hours,
            "max_cache_size": self.max_cache_size,
            "auto_cleanup": self.auto_cleanup,
            "cleanup_interval_hours": self.cleanup_interval_hours,
            "compression_enabled": self.compression_enabled,
            "encryption_enabled": self.encryption_enabled,
            "encryption_key": self.encryption_key,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersistenceConfig":
        """Create from dictionary."""
        return cls(
            storage_format=StorageFormat(data["storage_format"]),
            storage_path=data["storage_path"],
            cache_enabled=data["cache_enabled"],
            cache_strategy=CacheStrategy(data["cache_strategy"]),
            cache_ttl_hours=data["cache_ttl_hours"],
            max_cache_size=data["max_cache_size"],
            auto_cleanup=data["auto_cleanup"],
            cleanup_interval_hours=data["cleanup_interval_hours"],
            compression_enabled=data["compression_enabled"],
            encryption_enabled=data["encryption_enabled"],
            encryption_key=data.get("encryption_key"),
        )
