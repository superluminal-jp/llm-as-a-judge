"""
Unit tests for batch processing domain models.

Tests the core domain entities and value objects for batch evaluation processing,
including validation, business rules, and data integrity.
"""

import pytest
from datetime import datetime
from uuid import uuid4

from src.llm_judge.domain.batch.models import (
    BatchRequest,
    BatchResult,
    BatchStatus,
    BatchEvaluationItem,
    BatchProgress,
    EvaluationType,
)
from src.llm_judge.domain.models import (
    CandidateResponse,
    EvaluationResult,
)


class TestBatchEvaluationItem:
    """Test BatchEvaluationItem domain model."""

    def test_create_single_evaluation_item(self):
        """Test creating a single evaluation item."""
        candidate = CandidateResponse(
            prompt="What is AI?",
            response="AI is artificial intelligence",
            model="test-model",
        )

        item = BatchEvaluationItem(
            evaluation_type=EvaluationType.SINGLE,
            candidate_response=candidate,
            criteria="accuracy",
        )

        assert item.evaluation_type == EvaluationType.SINGLE
        assert item.candidate_response == candidate
        assert item.criteria == "accuracy"
        assert item.candidate_a is None
        assert item.candidate_b is None
        assert item.result is None
        assert item.error is None
        assert item.processed_at is None
        assert item.processing_duration is None
        assert item.priority == 0
        assert item.metadata == {}

    def test_create_comparison_evaluation_item(self):
        """Test creating a comparison evaluation item."""
        candidate_a = CandidateResponse(
            prompt="What is AI?",
            response="AI is artificial intelligence",
            model="model-a",
        )
        candidate_b = CandidateResponse(
            prompt="What is AI?",
            response="Artificial Intelligence is the simulation of human intelligence",
            model="model-b",
        )

        item = BatchEvaluationItem(
            evaluation_type=EvaluationType.COMPARISON,
            candidate_a=candidate_a,
            candidate_b=candidate_b,
        )

        assert item.evaluation_type == EvaluationType.COMPARISON
        assert item.candidate_a == candidate_a
        assert item.candidate_b == candidate_b
        assert item.candidate_response is None
        assert item.criteria == "overall quality"

    def test_single_evaluation_requires_candidate_response(self):
        """Test that single evaluation requires candidate_response."""
        with pytest.raises(
            ValueError, match="Single evaluation requires candidate_response"
        ):
            BatchEvaluationItem(
                evaluation_type=EvaluationType.SINGLE, candidate_response=None
            )

    def test_comparison_evaluation_requires_both_candidates(self):
        """Test that comparison evaluation requires both candidates."""
        candidate_a = CandidateResponse("What is AI?", "AI is artificial intelligence")

        with pytest.raises(
            ValueError,
            match="Comparison evaluation requires both candidate_a and candidate_b",
        ):
            BatchEvaluationItem(
                evaluation_type=EvaluationType.COMPARISON,
                candidate_a=candidate_a,
                candidate_b=None,
            )

    def test_comparison_candidates_must_have_same_prompt(self):
        """Test that comparison candidates must have the same prompt."""
        candidate_a = CandidateResponse("What is AI?", "AI is artificial intelligence")
        candidate_b = CandidateResponse("What is ML?", "ML is machine learning")

        with pytest.raises(
            ValueError, match="Comparison candidates must have the same prompt"
        ):
            BatchEvaluationItem(
                evaluation_type=EvaluationType.COMPARISON,
                candidate_a=candidate_a,
                candidate_b=candidate_b,
            )

    def test_item_id_generation(self):
        """Test that item IDs are automatically generated."""
        candidate = CandidateResponse("What is AI?", "AI is artificial intelligence")

        item1 = BatchEvaluationItem(
            evaluation_type=EvaluationType.SINGLE, candidate_response=candidate
        )
        item2 = BatchEvaluationItem(
            evaluation_type=EvaluationType.SINGLE, candidate_response=candidate
        )

        assert item1.item_id != item2.item_id
        assert len(item1.item_id) > 0

    def test_is_completed_property(self):
        """Test the is_completed property."""
        candidate = CandidateResponse("What is AI?", "AI is artificial intelligence")
        item = BatchEvaluationItem(
            evaluation_type=EvaluationType.SINGLE, candidate_response=candidate
        )

        # Initially not completed
        assert not item.is_completed

        # Completed with result
        item.result = EvaluationResult(4.0, "Good response")
        assert item.is_completed

        # Completed with error
        item.result = None
        item.error = "Processing failed"
        assert item.is_completed

    def test_has_error_property(self):
        """Test the has_error property."""
        candidate = CandidateResponse("What is AI?", "AI is artificial intelligence")
        item = BatchEvaluationItem(
            evaluation_type=EvaluationType.SINGLE, candidate_response=candidate
        )

        # Initially no error
        assert not item.has_error

        # Has error
        item.error = "Processing failed"
        assert item.has_error


class TestBatchRequest:
    """Test BatchRequest domain model."""

    def test_create_batch_request(self):
        """Test creating a batch request."""
        batch = BatchRequest(
            name="Test Batch",
            description="Test batch for unit testing",
            max_concurrent_items=5,
        )

        assert batch.name == "Test Batch"
        assert batch.description == "Test batch for unit testing"
        assert batch.max_concurrent_items == 5
        assert batch.retry_failed_items is True
        assert batch.max_retries_per_item == 3
        assert batch.continue_on_error is True
        assert batch.total_items == 0
        assert len(batch.items) == 0

    def test_batch_id_generation(self):
        """Test that batch IDs are automatically generated."""
        batch1 = BatchRequest()
        batch2 = BatchRequest()

        assert batch1.batch_id != batch2.batch_id
        assert len(batch1.batch_id) > 0

    def test_created_at_timestamp(self):
        """Test that created_at timestamp is set."""
        before = datetime.now()
        batch = BatchRequest()
        after = datetime.now()

        assert before <= batch.created_at <= after

    def test_validation_max_concurrent_items(self):
        """Test validation of max_concurrent_items."""
        with pytest.raises(
            ValueError, match="max_concurrent_items must be greater than 0"
        ):
            BatchRequest(max_concurrent_items=0)

        with pytest.raises(
            ValueError, match="max_concurrent_items must be greater than 0"
        ):
            BatchRequest(max_concurrent_items=-1)

    def test_validation_max_retries_per_item(self):
        """Test validation of max_retries_per_item."""
        with pytest.raises(ValueError, match="max_retries_per_item cannot be negative"):
            BatchRequest(max_retries_per_item=-1)

    def test_add_single_evaluation(self):
        """Test adding a single evaluation to the batch."""
        batch = BatchRequest()
        candidate = CandidateResponse("What is AI?", "AI is artificial intelligence")

        item_id = batch.add_single_evaluation(
            candidate=candidate,
            criteria="accuracy",
            priority=1,
            metadata={"test": True},
        )

        assert batch.total_items == 1
        assert len(batch.items) == 1

        item = batch.items[0]
        assert item.item_id == item_id
        assert item.evaluation_type == EvaluationType.SINGLE
        assert item.candidate_response == candidate
        assert item.criteria == "accuracy"
        assert item.priority == 1
        assert item.metadata == {"test": True}

    def test_add_comparison_evaluation(self):
        """Test adding a comparison evaluation to the batch."""
        batch = BatchRequest()
        candidate_a = CandidateResponse("What is AI?", "AI is artificial intelligence")
        candidate_b = CandidateResponse("What is AI?", "Artificial Intelligence is...")

        item_id = batch.add_comparison_evaluation(
            candidate_a=candidate_a,
            candidate_b=candidate_b,
            priority=2,
            metadata={"comparison": True},
        )

        assert batch.total_items == 1
        assert len(batch.items) == 1

        item = batch.items[0]
        assert item.item_id == item_id
        assert item.evaluation_type == EvaluationType.COMPARISON
        assert item.candidate_a == candidate_a
        assert item.candidate_b == candidate_b
        assert item.priority == 2
        assert item.metadata == {"comparison": True}

    def test_get_items_by_priority(self):
        """Test getting items sorted by priority."""
        batch = BatchRequest()
        candidate = CandidateResponse("What is AI?", "AI is artificial intelligence")

        # Add items with different priorities
        batch.add_single_evaluation(candidate, priority=3)
        batch.add_single_evaluation(candidate, priority=1)
        batch.add_single_evaluation(candidate, priority=2)

        sorted_items = batch.get_items_by_priority()

        assert len(sorted_items) == 3
        assert sorted_items[0].priority == 3  # Highest priority first (reverse order)
        assert sorted_items[1].priority == 2
        assert sorted_items[2].priority == 1

    def test_single_evaluations_property(self):
        """Test the single_evaluations property."""
        batch = BatchRequest()
        candidate = CandidateResponse("What is AI?", "AI is artificial intelligence")

        batch.add_single_evaluation(candidate)
        batch.add_single_evaluation(candidate)

        single_evals = batch.single_evaluations
        assert len(single_evals) == 2
        assert all(
            item.evaluation_type == EvaluationType.SINGLE for item in single_evals
        )

    def test_comparison_evaluations_property(self):
        """Test the comparison_evaluations property."""
        batch = BatchRequest()
        candidate_a = CandidateResponse("What is AI?", "AI is artificial intelligence")
        candidate_b = CandidateResponse("What is AI?", "Artificial Intelligence is...")

        batch.add_comparison_evaluation(candidate_a, candidate_b)
        batch.add_comparison_evaluation(candidate_a, candidate_b)

        comparison_evals = batch.comparison_evaluations
        assert len(comparison_evals) == 2
        assert all(
            item.evaluation_type == EvaluationType.COMPARISON
            for item in comparison_evals
        )


class TestBatchProgress:
    """Test BatchProgress domain model."""

    def test_create_batch_progress(self):
        """Test creating batch progress."""
        batch_id = str(uuid4())
        started_at = datetime.now()

        progress = BatchProgress(
            batch_id=batch_id, total_items=10, started_at=started_at
        )

        assert progress.batch_id == batch_id
        assert progress.total_items == 10
        assert progress.started_at == started_at
        assert progress.processing_items == 0
        assert progress.completed_items == 0
        assert progress.failed_items == 0
        assert progress.pending_items == 10
        assert progress.items_per_second is None
        assert progress.estimated_completion is None

    def test_pending_items_calculation(self):
        """Test pending items calculation."""
        progress = BatchProgress(
            batch_id="test", total_items=10, started_at=datetime.now()
        )

        # Initially all items are pending
        assert progress.pending_items == 10

        # Update progress
        progress.processing_items = 2
        progress.completed_items = 3
        progress.failed_items = 1

        # Pending = total - processing - completed - failed
        assert progress.pending_items == 4

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        progress = BatchProgress(
            batch_id="test", total_items=10, started_at=datetime.now()
        )

        # No items processed yet
        assert progress.success_rate == 0.0

        # Some items completed
        progress.completed_items = 3
        progress.failed_items = 1
        processed = progress.completed_items + progress.failed_items

        expected_rate = progress.completed_items / processed
        assert progress.success_rate == expected_rate


class TestBatchResult:
    """Test BatchResult domain model."""

    def test_create_batch_result(self):
        """Test creating a batch result."""
        batch_request = BatchRequest(name="Test Batch")
        started_at = datetime.now()
        completed_at = datetime.now()

        result = BatchResult(
            batch_request=batch_request,
            status=BatchStatus.COMPLETED,
            started_at=started_at,
            completed_at=completed_at,
            processing_duration=10.5,
        )

        assert result.batch_request == batch_request
        assert result.status == BatchStatus.COMPLETED
        assert result.started_at == started_at
        assert result.completed_at == completed_at
        assert result.processing_duration == 10.5
        assert len(result.successful_items) == 0
        assert len(result.failed_items) == 0

    def test_total_items_property(self):
        """Test the total_items property."""
        batch_request = BatchRequest()
        candidate = CandidateResponse("What is AI?", "AI is artificial intelligence")
        batch_request.add_single_evaluation(candidate)
        batch_request.add_single_evaluation(candidate)

        result = BatchResult(
            batch_request=batch_request,
            status=BatchStatus.COMPLETED,
            started_at=datetime.now(),
        )

        assert result.total_items == 2

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        batch_request = BatchRequest()
        candidate = CandidateResponse("What is AI?", "AI is artificial intelligence")
        batch_request.add_single_evaluation(candidate)
        batch_request.add_single_evaluation(candidate)

        # Create successful and failed items
        successful_item = BatchEvaluationItem(
            evaluation_type=EvaluationType.SINGLE, candidate_response=candidate
        )
        successful_item.result = EvaluationResult(4.0, "Good")

        failed_item = BatchEvaluationItem(
            evaluation_type=EvaluationType.SINGLE, candidate_response=candidate
        )
        failed_item.error = "Failed"

        result = BatchResult(
            batch_request=batch_request,
            status=BatchStatus.COMPLETED,
            started_at=datetime.now(),
            successful_items=[successful_item],
            failed_items=[failed_item],
        )

        # Success rate = successful / total
        assert result.success_rate == 0.5

    def test_success_rate_with_no_items(self):
        """Test success rate with no items."""
        batch_request = BatchRequest()
        result = BatchResult(
            batch_request=batch_request,
            status=BatchStatus.COMPLETED,
            started_at=datetime.now(),
        )

        # Should be 1.0 (100%) when no items
        assert result.success_rate == 1.0

    def test_is_completed_property(self):
        """Test the is_completed property."""
        batch_request = BatchRequest()

        # Completed status
        result = BatchResult(
            batch_request=batch_request,
            status=BatchStatus.COMPLETED,
            started_at=datetime.now(),
        )
        assert result.is_completed

        # Failed status
        result.status = BatchStatus.FAILED
        assert result.is_completed

        # Cancelled status
        result.status = BatchStatus.CANCELLED
        assert result.is_completed

        # Processing status
        result.status = BatchStatus.PROCESSING
        assert not result.is_completed

        # Pending status
        result.status = BatchStatus.PENDING
        assert not result.is_completed

    def test_get_results_by_type(self):
        """Test getting results filtered by evaluation type."""
        batch_request = BatchRequest()
        candidate = CandidateResponse("What is AI?", "AI is artificial intelligence")

        # Create items of different types
        single_item = BatchEvaluationItem(
            evaluation_type=EvaluationType.SINGLE, candidate_response=candidate
        )
        single_item.result = EvaluationResult(4.0, "Good")

        comparison_item = BatchEvaluationItem(
            evaluation_type=EvaluationType.COMPARISON,
            candidate_a=candidate,
            candidate_b=candidate,
        )
        comparison_item.result = {"winner": "A"}

        result = BatchResult(
            batch_request=batch_request,
            status=BatchStatus.COMPLETED,
            started_at=datetime.now(),
            successful_items=[single_item, comparison_item],
        )

        # Filter by type
        single_results = result.get_results_by_type(EvaluationType.SINGLE)
        comparison_results = result.get_results_by_type(EvaluationType.COMPARISON)

        assert len(single_results) == 1
        assert single_results[0].evaluation_type == EvaluationType.SINGLE

        assert len(comparison_results) == 1
        assert comparison_results[0].evaluation_type == EvaluationType.COMPARISON

    def test_get_summary(self):
        """Test getting batch result summary."""
        batch_request = BatchRequest(name="Test Batch")
        candidate = CandidateResponse("What is AI?", "AI is artificial intelligence")

        # Add items to batch request to make total_items > 0
        batch_request.add_single_evaluation(candidate, criteria="accuracy")
        batch_request.add_single_evaluation(candidate, criteria="clarity")

        # Create successful and failed items
        successful_item = BatchEvaluationItem(
            evaluation_type=EvaluationType.SINGLE, candidate_response=candidate
        )
        successful_item.result = EvaluationResult(4.0, "Good")
        successful_item.processed_at = datetime.now()
        successful_item.processing_duration = 1.5

        failed_item = BatchEvaluationItem(
            evaluation_type=EvaluationType.SINGLE, candidate_response=candidate
        )
        failed_item.error = "Failed"
        failed_item.processed_at = datetime.now()
        failed_item.processing_duration = 0.5

        result = BatchResult(
            batch_request=batch_request,
            status=BatchStatus.COMPLETED,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            processing_duration=10.0,
            successful_items=[successful_item],
            failed_items=[failed_item],
            average_processing_time=1.0,
        )

        summary = result.get_summary()

        assert summary["batch_id"] == batch_request.batch_id
        assert summary["status"] == "completed"
        assert summary["total_items"] == 2  # Two items in batch_request
        assert summary["successful_items"] == 1
        assert summary["failed_items"] == 1
        assert summary["success_rate"] == 0.5
        assert summary["processing_duration"] == 10.0
        assert summary["average_processing_time"] == 1.0
