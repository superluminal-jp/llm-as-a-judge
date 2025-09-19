"""
Unit tests for persistence infrastructure components.
"""

import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.llm_judge.domain.persistence.models import (
    PersistenceConfig,
    EvaluationRecord,
)
from src.llm_judge.domain.evaluation.results import (
    MultiCriteriaResult,
    CriterionScore,
    AggregatedScore,
)

# CandidateResponse will be imported where needed to avoid circular imports
from src.llm_judge.infrastructure.persistence.json_repository import (
    JsonEvaluationRepository,
)
from src.llm_judge.infrastructure.persistence.persistence_service import (
    PersistenceServiceImpl,
)


class TestPersistenceConfig:
    """Test PersistenceConfig model."""

    def test_default_values(self):
        """Test default configuration values."""
        config = PersistenceConfig()

        assert config.storage_path == "./data"
        assert config.cache_enabled is True
        assert config.cache_ttl_hours == 24
        assert config.max_cache_size == 1000
        assert config.auto_cleanup is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = PersistenceConfig(
            storage_path="/custom/path",
            cache_enabled=False,
            cache_ttl_hours=48,
            max_cache_size=500,
            auto_cleanup=False,
        )

        assert config.storage_path == "/custom/path"
        assert config.cache_enabled is False
        assert config.cache_ttl_hours == 48
        assert config.max_cache_size == 500
        assert config.auto_cleanup is False


class TestEvaluationRecord:
    """Test EvaluationRecord model."""

    def test_creation(self):
        """Test EvaluationRecord creation."""
        from src.llm_judge.application.services.llm_judge_service import (
            CandidateResponse,
        )

        candidate = CandidateResponse(
            prompt="Test prompt",
            response="Test response",
        )

        result = MultiCriteriaResult(
            criterion_scores={
                "accuracy": CriterionScore(
                    criterion_name="accuracy", score=4.0, reasoning="Good"
                ),
                "clarity": CriterionScore(
                    criterion_name="clarity", score=3.5, reasoning="Fair"
                ),
            },
            aggregated=AggregatedScore(overall_score=3.75),
        )

        record = EvaluationRecord(
            id=str(uuid.uuid4()),
            candidate=candidate,
            result=result,
            criteria_hash="test_hash",
            judge_model="gpt-4",
            provider="openai",
            evaluation_time_ms=1234567890,
            evaluated_at=datetime.now(timezone.utc),
        )

        assert record.candidate == candidate
        assert record.result == result
        assert record.criteria_hash == "test_hash"
        assert record.judge_model == "gpt-4"
        assert record.provider == "openai"
        assert record.evaluation_time_ms == 1234567890

    def test_to_dict(self):
        """Test EvaluationRecord serialization."""
        from src.llm_judge.application.services.llm_judge_service import (
            CandidateResponse,
        )

        candidate = CandidateResponse(
            prompt="Test prompt",
            response="Test response",
        )

        result = MultiCriteriaResult(
            criterion_scores={
                "accuracy": CriterionScore(
                    criterion_name="accuracy", score=4.0, reasoning="Good"
                ),
            },
            aggregated=AggregatedScore(overall_score=4.0),
        )

        record = EvaluationRecord(
            id="test-id",
            candidate=candidate,
            result=result,
            criteria_hash="test_hash",
            judge_model="gpt-4",
            provider="openai",
            evaluation_time_ms=1234567890,
            evaluated_at=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        data = record.to_dict()

        assert data["id"] == "test-id"
        assert data["candidate"]["prompt"] == "Test prompt"
        assert data["candidate"]["response"] == "Test response"
        assert data["result"]["aggregated"]["overall_score"] == 4.0
        assert data["criteria_hash"] == "test_hash"
        assert data["judge_model"] == "gpt-4"
        assert data["provider"] == "openai"
        assert data["evaluation_time_ms"] == 1234567890
        assert data["evaluated_at"] == "2023-01-01T12:00:00+00:00"

    def test_from_dict(self):
        """Test EvaluationRecord deserialization."""
        from src.llm_judge.application.services.llm_judge_service import (
            CandidateResponse,
        )

        data = {
            "id": "test-id",
            "candidate": {
                "prompt": "Test prompt",
                "response": "Test response",
            },
            "result": {
                "criterion_scores": {
                    "accuracy": {
                        "score": 4.0,
                        "reasoning": "Good",
                    },
                },
                "aggregated": {
                    "overall_score": 4.0,
                },
            },
            "criteria_hash": "test_hash",
            "judge_model": "gpt-4",
            "provider": "openai",
            "evaluation_time_ms": 1234567890,
            "evaluated_at": "2023-01-01T12:00:00+00:00",
        }

        record = EvaluationRecord.from_dict(data)

        assert record.id == "test-id"
        assert record.candidate.prompt == "Test prompt"
        assert record.candidate.response == "Test response"
        assert record.result.aggregated.overall_score == 4.0
        assert record.criteria_hash == "test_hash"
        assert record.judge_model == "gpt-4"
        assert record.provider == "openai"
        assert record.evaluation_time_ms == 1234567890


class TestJsonEvaluationRepository:
    """Test JsonEvaluationRepository implementation."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def repository(self, temp_dir):
        """Create repository instance for testing."""
        return JsonEvaluationRepository(storage_path=str(temp_dir))

    @pytest.fixture
    def sample_record(self):
        """Create sample evaluation record."""
        from src.llm_judge.application.services.llm_judge_service import (
            CandidateResponse,
        )

        candidate = CandidateResponse(
            prompt="Test prompt",
            response="Test response",
        )

        result = MultiCriteriaResult(
            criterion_scores={
                "accuracy": CriterionScore(
                    criterion_name="accuracy", score=4.0, reasoning="Good"
                ),
            },
            aggregated=AggregatedScore(overall_score=4.0),
        )

        return EvaluationRecord(
            id="test-id",
            candidate=candidate,
            result=result,
            criteria_hash="test_hash",
            judge_model="gpt-4",
            provider="openai",
            evaluation_time_ms=1234567890,
            evaluated_at=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_save_evaluation(self, repository, sample_record):
        """Test saving evaluation record."""
        await repository.save_evaluation(sample_record)

        # Verify file was created
        storage_path = Path(repository.storage_path)
        assert storage_path.exists()

        # Verify content
        with open(storage_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["test-id"]["id"] == "test-id"
        assert data["test-id"]["candidate"]["prompt"] == "Test prompt"

    @pytest.mark.asyncio
    async def test_get_evaluation(self, repository, sample_record):
        """Test retrieving evaluation record."""
        await repository.save_evaluation(sample_record)

        retrieved = await repository.get_evaluation("test-id")

        assert retrieved is not None
        assert retrieved.id == "test-id"
        assert retrieved.candidate.prompt == "Test prompt"

    @pytest.mark.asyncio
    async def test_get_evaluation_not_found(self, repository):
        """Test retrieving non-existent evaluation record."""
        retrieved = await repository.get_evaluation("non-existent")

        assert retrieved is None

    @pytest.mark.asyncio
    async def test_list_evaluations(self, repository, sample_record):
        """Test listing evaluation records."""
        # Add multiple records
        record1 = sample_record
        record2 = EvaluationRecord(
            id="test-id-2",
            candidate=sample_record.candidate,
            result=sample_record.result,
            criteria_hash="test_hash_2",
            judge_model="claude-3",
            provider="anthropic",
            evaluation_time_ms=1234567891,
            evaluated_at=datetime.now(timezone.utc),
        )

        await repository.save_evaluation(record1)
        await repository.save_evaluation(record2)

        records = await repository.list_evaluations()

        assert len(records) == 2
        assert any(r.id == "test-id" for r in records)
        assert any(r.id == "test-id-2" for r in records)

    @pytest.mark.asyncio
    async def test_list_evaluations_with_limit(self, repository, sample_record):
        """Test listing evaluation records with limit."""
        # Add multiple records
        for i in range(5):
            record = EvaluationRecord(
                id=f"test-id-{i}",
                candidate=sample_record.candidate,
                result=sample_record.result,
                criteria_hash=f"test_hash_{i}",
                judge_model="gpt-4",
                provider="openai",
                evaluation_time_ms=1234567890 + i,
                evaluated_at=datetime.now(timezone.utc),
            )
            await repository.save_evaluation(record)

        records = await repository.list_evaluations(limit=3)

        assert len(records) == 3

    @pytest.mark.asyncio
    async def test_delete_evaluation(self, repository, sample_record):
        """Test deleting evaluation record."""
        await repository.save_evaluation(sample_record)

        # Verify record exists
        retrieved = await repository.get_evaluation("test-id")
        assert retrieved is not None

        # Delete record
        await repository.delete_evaluation("test-id")

        # Verify record is deleted
        retrieved = await repository.get_evaluation("test-id")
        assert retrieved is None


class TestPersistenceServiceImpl:
    """Test PersistenceServiceImpl."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def config(self, temp_dir):
        """Create persistence config for testing."""
        return PersistenceConfig(
            storage_path=str(temp_dir),
            cache_enabled=True,
            cache_ttl_hours=1,
            max_cache_size=10,
            auto_cleanup=True,
        )

    @pytest.fixture
    def service(self, config):
        """Create persistence service for testing."""
        return PersistenceServiceImpl(config)

    @pytest.fixture
    def sample_candidate(self):
        """Create sample candidate response."""
        from src.llm_judge.application.services.llm_judge_service import (
            CandidateResponse,
        )

        return CandidateResponse(
            prompt="Test prompt",
            response="Test response",
        )

    @pytest.fixture
    def sample_result(self):
        """Create sample evaluation result."""
        return MultiCriteriaResult(
            criterion_scores={
                "accuracy": CriterionScore(
                    criterion_name="accuracy", score=4.0, reasoning="Good"
                ),
            },
            aggregated=AggregatedScore(overall_score=4.0),
        )

    @pytest.mark.asyncio
    async def test_save_evaluation(self, service, sample_candidate, sample_result):
        """Test saving evaluation."""
        await service.save_evaluation(
            candidate=sample_candidate,
            result=sample_result,
            criteria_hash="test_hash",
            judge_model="gpt-4",
            provider="openai",
            evaluation_time_ms=1234567890,
            metadata={"test": "value"},
        )

        # Verify record was saved
        records = await service.list_evaluations()
        assert len(records) == 1
        assert records[0].candidate.prompt == "Test prompt"

    @pytest.mark.asyncio
    async def test_get_evaluation_cache_hit(
        self, service, sample_candidate, sample_result
    ):
        """Test getting evaluation from cache."""
        # Save evaluation
        await service.save_evaluation(
            candidate=sample_candidate,
            result=sample_result,
            criteria_hash="test_hash",
            judge_model="gpt-4",
            provider="openai",
            evaluation_time_ms=1234567890,
        )

        # Get evaluation (should hit cache)
        cached = await service.get_evaluation(
            prompt=sample_candidate.prompt,
            response=sample_candidate.response,
            criteria_hash="test_hash",
            judge_model="gpt-4",
        )

        assert cached is not None
        assert cached.result.aggregated.overall_score == 4.0

    @pytest.mark.asyncio
    async def test_get_evaluation_cache_miss(self, service):
        """Test getting evaluation when not in cache."""
        cached = await service.get_evaluation(
            prompt="Non-existent prompt",
            response="Non-existent response",
            criteria_hash="non-existent",
            judge_model="gpt-4",
        )

        assert cached is None

    @pytest.mark.asyncio
    async def test_clean_cache(self, service, sample_candidate, sample_result):
        """Test cache cleanup."""
        # Save evaluation
        await service.save_evaluation(
            candidate=sample_candidate,
            result=sample_result,
            criteria_hash="test_hash",
            judge_model="gpt-4",
            provider="openai",
            evaluation_time_ms=1234567890,
        )

        # Verify cache has entry
        cached = await service.get_evaluation(
            prompt=sample_candidate.prompt,
            response=sample_candidate.response,
            criteria_hash="test_hash",
            judge_model="gpt-4",
        )
        assert cached is not None

        # Clean cache
        await service.clean_cache()

        # Verify cache is empty
        cached = await service.get_evaluation(
            prompt=sample_candidate.prompt,
            response=sample_candidate.response,
            criteria_hash="test_hash",
            judge_model="gpt-4",
        )
        assert cached is None

    @pytest.mark.asyncio
    async def test_list_evaluations(self, service, sample_candidate, sample_result):
        """Test listing evaluations."""
        # Save multiple evaluations
        for i in range(3):
            candidate = CandidateResponse(
                prompt=f"Test prompt {i}",
                response=f"Test response {i}",
            )
            await service.save_evaluation(
                candidate=candidate,
                result=sample_result,
                criteria_hash=f"test_hash_{i}",
                judge_model="gpt-4",
                provider="openai",
                evaluation_time_ms=1234567890 + i,
            )

        records = await service.list_evaluations(limit=2)

        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self, service, sample_candidate, sample_result):
        """Test cache TTL expiration."""
        # Create service with very short TTL
        short_ttl_config = PersistenceConfig(
            storage_path=service.repository.storage_path,
            cache_enabled=True,
            cache_ttl_hours=0,  # 0 hours = immediate expiration
            max_cache_size=10,
            auto_cleanup=True,
        )
        short_ttl_service = PersistenceServiceImpl(short_ttl_config)

        # Save evaluation
        await short_ttl_service.save_evaluation(
            candidate=sample_candidate,
            result=sample_result,
            criteria_hash="test_hash",
            judge_model="gpt-4",
            provider="openai",
            evaluation_time_ms=1234567890,
        )

        # Try to get from cache (should be expired)
        cached = await short_ttl_service.get_evaluation(
            prompt=sample_candidate.prompt,
            response=sample_candidate.response,
            criteria_hash="test_hash",
            judge_model="gpt-4",
        )

        # Should return None due to TTL expiration
        assert cached is None
