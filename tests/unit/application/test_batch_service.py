"""
Unit tests for batch processing application service.

Tests the application service that orchestrates batch evaluation processing
by coordinating between domain services and infrastructure components.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, mock_open

from src.llm_judge.application.services.batch_service import BatchProcessingService
from src.llm_judge.application.services.llm_judge_service import (
    LLMJudge,
    CandidateResponse,
    EvaluationResult,
)
from src.llm_judge.domain.batch.models import (
    BatchRequest,
    BatchResult,
    BatchStatus,
    BatchEvaluationItem,
    BatchProgress,
    EvaluationType,
)
from src.llm_judge.domain.evaluation.results import (
    MultiCriteriaResult,
    AggregatedScore,
    CriterionScore,
)


class TestBatchProcessingService:
    """Test BatchProcessingService application service."""

    @pytest.fixture
    def mock_llm_judge(self):
        """Create a mock LLM judge for testing."""
        judge = Mock(spec=LLMJudge)

        # Mock multi-criteria evaluation
        mock_multi_result = Mock(spec=MultiCriteriaResult)
        mock_multi_result.aggregated = Mock(spec=AggregatedScore)
        mock_multi_result.aggregated.overall_score = 4.2
        mock_multi_result.aggregated.confidence = 0.85
        mock_multi_result.overall_reasoning = "Good multi-criteria evaluation"
        mock_multi_result.criterion_scores = [
            Mock(
                spec=CriterionScore,
                criterion_name="accuracy",
                score=4.0,
                reasoning="Good accuracy",
            ),
            Mock(
                spec=CriterionScore,
                criterion_name="clarity",
                score=4.5,
                reasoning="Very clear",
            ),
        ]

        judge.evaluate_multi_criteria = AsyncMock(return_value=mock_multi_result)

        # Mock comparison evaluation
        judge.compare_responses = AsyncMock(
            return_value={
                "winner": "A",
                "reasoning": "Response A is better",
                "confidence": 0.8,
            }
        )

        return judge

    @pytest.fixture
    def batch_service(self, mock_llm_judge):
        """Create a batch processing service for testing."""
        return BatchProcessingService(llm_judge=mock_llm_judge, max_workers=5)

    @pytest.fixture
    def sample_batch_request(self):
        """Create a sample batch request for testing."""
        batch = BatchRequest(
            name="Test Batch", max_concurrent_items=3, max_retries_per_item=2
        )

        candidate = CandidateResponse(
            prompt="What is AI?",
            response="AI is artificial intelligence",
            model="test-model",
        )

        # Add some test items
        batch.add_single_evaluation(candidate, criteria="accuracy", priority=1)
        batch.add_single_evaluation(candidate, criteria="clarity", priority=2)

        return batch

    @pytest.mark.asyncio
    async def test_process_batch_request_success(
        self, batch_service, sample_batch_request
    ):
        """Test successful batch request processing."""
        result = await batch_service.process_batch_request(sample_batch_request)

        assert isinstance(result, BatchResult)
        assert result.status == BatchStatus.COMPLETED
        assert result.batch_request == sample_batch_request
        assert result.completed_items_count == 2
        assert result.failed_items_count == 0
        assert result.success_rate == 1.0

    @pytest.mark.asyncio
    async def test_process_batch_request_with_progress_callback(
        self, batch_service, sample_batch_request
    ):
        """Test batch processing with progress callback."""
        progress_updates = []

        def progress_callback(progress: BatchProgress):
            progress_updates.append(progress)

        result = await batch_service.process_batch_request(
            sample_batch_request, progress_callback=progress_callback
        )

        assert result.status == BatchStatus.COMPLETED
        assert len(progress_updates) > 0

        # Check that progress was updated
        final_progress = progress_updates[-1]
        assert final_progress.completed_items == 2

    @pytest.mark.asyncio
    async def test_process_batch_request_with_comparison_evaluations(
        self, batch_service, mock_llm_judge
    ):
        """Test batch processing with comparison evaluations."""
        batch = BatchRequest(max_concurrent_items=2)

        candidate_a = CandidateResponse("What is AI?", "AI is artificial intelligence")
        candidate_b = CandidateResponse("What is AI?", "Artificial Intelligence is...")

        batch.add_comparison_evaluation(candidate_a, candidate_b)

        result = await batch_service.process_batch_request(batch)

        assert result.status == BatchStatus.COMPLETED
        assert result.completed_items_count == 1

        # Verify comparison was called
        mock_llm_judge.compare_responses.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_batch_from_file_jsonl(self, batch_service, mock_llm_judge):
        """Test processing batch from JSONL file."""
        # Create temporary JSONL file
        jsonl_content = [
            '{"type": "single", "prompt": "What is AI?", "response": "AI is artificial intelligence", "model": "test-model", "criteria": "accuracy"}',
            '{"type": "single", "prompt": "What is ML?", "response": "ML is machine learning", "model": "test-model", "criteria": "clarity"}',
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("\n".join(jsonl_content))
            temp_file = f.name

        try:
            result = await batch_service.process_batch_from_file(temp_file)

            assert isinstance(result, BatchResult)
            assert result.status == BatchStatus.COMPLETED
            assert result.completed_items_count == 2

            # Verify multi-criteria evaluation was called
            assert mock_llm_judge.evaluate_multi_criteria.call_count == 2

        finally:
            Path(temp_file).unlink()

    @pytest.mark.asyncio
    async def test_process_batch_from_file_csv(self, batch_service, mock_llm_judge):
        """Test processing batch from CSV file."""
        # Create temporary CSV file
        csv_content = """type,prompt,response,model,criteria
single,"What is AI?","AI is artificial intelligence","test-model","accuracy"
single,"What is ML?","ML is machine learning","test-model","clarity"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = f.name

        try:
            result = await batch_service.process_batch_from_file(temp_file)

            assert isinstance(result, BatchResult)
            assert result.status == BatchStatus.COMPLETED
            assert result.completed_items_count == 2

        finally:
            Path(temp_file).unlink()

    @pytest.mark.asyncio
    async def test_process_batch_from_file_json(self, batch_service, mock_llm_judge):
        """Test processing batch from JSON file."""
        # Create temporary JSON file
        json_content = {
            "items": [
                {
                    "type": "single",
                    "prompt": "What is AI?",
                    "response": "AI is artificial intelligence",
                    "model": "test-model",
                    "criteria": "accuracy",
                },
                {
                    "type": "single",
                    "prompt": "What is ML?",
                    "response": "ML is machine learning",
                    "model": "test-model",
                    "criteria": "clarity",
                },
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            temp_file = f.name

        try:
            result = await batch_service.process_batch_from_file(temp_file)

            assert isinstance(result, BatchResult)
            assert result.status == BatchStatus.COMPLETED
            assert result.completed_items_count == 2

        finally:
            Path(temp_file).unlink()

    @pytest.mark.asyncio
    async def test_process_batch_from_file_with_output(
        self, batch_service, mock_llm_judge
    ):
        """Test processing batch from file with output."""
        # Create temporary input file
        jsonl_content = [
            '{"type": "single", "prompt": "What is AI?", "response": "AI is artificial intelligence", "model": "test-model"}'
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("\n".join(jsonl_content))
            input_file = f.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            output_file = f.name

        try:
            result = await batch_service.process_batch_from_file(
                file_path=input_file, output_path=output_file
            )

            assert isinstance(result, BatchResult)
            assert result.status == BatchStatus.COMPLETED

            # Check that output file was created
            assert Path(output_file).exists()

            # Check output file content
            with open(output_file, "r") as f:
                output_data = json.load(f)

            assert "batch_summary" in output_data
            assert "results" in output_data
            assert len(output_data["results"]) == 1

        finally:
            Path(input_file).unlink()
            Path(output_file).unlink()

    @pytest.mark.asyncio
    async def test_process_batch_from_file_with_batch_config(
        self, batch_service, mock_llm_judge
    ):
        """Test processing batch from file with custom batch configuration."""
        # Create temporary input file
        jsonl_content = [
            '{"type": "single", "prompt": "What is AI?", "response": "AI is artificial intelligence", "model": "test-model"}'
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("\n".join(jsonl_content))
            temp_file = f.name

        batch_config = {
            "name": "Custom Batch",
            "max_concurrent_items": 2,
            "retry_failed_items": False,
            "judge_provider": "openai",
            "judge_model": "gpt-4",
        }

        try:
            result = await batch_service.process_batch_from_file(
                file_path=temp_file, batch_config=batch_config
            )

            assert isinstance(result, BatchResult)
            assert result.status == BatchStatus.COMPLETED
            assert result.batch_request.name == "Custom Batch"
            assert result.batch_request.max_concurrent_items == 2
            assert result.batch_request.retry_failed_items is False

        finally:
            Path(temp_file).unlink()

    @pytest.mark.asyncio
    async def test_process_batch_from_file_nonexistent(self, batch_service):
        """Test processing batch from nonexistent file."""
        with pytest.raises(FileNotFoundError, match="Batch file not found"):
            await batch_service.process_batch_from_file("nonexistent.jsonl")

    @pytest.mark.asyncio
    async def test_process_batch_from_file_unsupported_format(self, batch_service):
        """Test processing batch from unsupported file format."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            temp_file = f.name

        try:
            with pytest.raises(ValueError, match="Unsupported file format"):
                await batch_service.process_batch_from_file(temp_file)
        finally:
            Path(temp_file).unlink()

    @pytest.mark.asyncio
    async def test_process_batch_from_file_invalid_jsonl(
        self, batch_service, mock_llm_judge
    ):
        """Test processing batch from file with invalid JSONL."""
        # Create temporary JSONL file with invalid JSON
        jsonl_content = [
            '{"type": "single", "prompt": "What is AI?", "response": "AI is artificial intelligence", "model": "test-model"}',
            "invalid json line",
            '{"type": "single", "prompt": "What is ML?", "response": "ML is machine learning", "model": "test-model"}',
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("\n".join(jsonl_content))
            temp_file = f.name

        try:
            result = await batch_service.process_batch_from_file(temp_file)

            # Should process valid lines and skip invalid ones
            assert isinstance(result, BatchResult)
            assert result.status == BatchStatus.COMPLETED
            assert result.completed_items_count == 2  # Only valid lines

        finally:
            Path(temp_file).unlink()

    @pytest.mark.asyncio
    async def test_process_batch_from_file_missing_required_fields(
        self, batch_service, mock_llm_judge
    ):
        """Test processing batch from file with missing required fields."""
        # Create temporary JSONL file with missing fields
        jsonl_content = [
            '{"type": "single", "prompt": "What is AI?"}',  # Missing response
            '{"type": "single", "response": "AI is artificial intelligence"}',  # Missing prompt
            '{"type": "single", "prompt": "What is ML?", "response": "ML is machine learning", "model": "test-model"}',  # Valid
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("\n".join(jsonl_content))
            temp_file = f.name

        try:
            result = await batch_service.process_batch_from_file(temp_file)

            # Should process valid lines and skip invalid ones
            assert isinstance(result, BatchResult)
            assert result.status == BatchStatus.COMPLETED
            assert result.completed_items_count == 1  # Only valid line

        finally:
            Path(temp_file).unlink()

    @pytest.mark.asyncio
    async def test_save_batch_results(self, batch_service, sample_batch_request):
        """Test saving batch results to file."""
        # Create a batch result
        successful_item = BatchEvaluationItem(
            evaluation_type=EvaluationType.SINGLE,
            candidate_response=CandidateResponse(
                "What is AI?", "AI is artificial intelligence"
            ),
            criteria="accuracy",
        )
        successful_item.result = EvaluationResult(4.0, "Good response", 0.8)
        successful_item.processed_at = None
        successful_item.processing_duration = 1.5

        result = BatchResult(
            batch_request=sample_batch_request,
            status=BatchStatus.COMPLETED,
            started_at=None,
            successful_items=[successful_item],
            failed_items=[],
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            output_file = f.name

        try:
            await batch_service._save_batch_results(result, Path(output_file))

            # Check that file was created
            assert Path(output_file).exists()

            # Check file content
            with open(output_file, "r") as f:
                output_data = json.load(f)

            assert "batch_summary" in output_data
            assert "results" in output_data
            assert len(output_data["results"]) == 1

            result_item = output_data["results"][0]
            assert result_item["status"] == "success"
            assert result_item["evaluation_type"] == "single"
            assert result_item["prompt"] == "What is AI?"
            assert result_item["response"] == "AI is artificial intelligence"

        finally:
            Path(output_file).unlink()

    def test_serialize_evaluation_result(self, batch_service):
        """Test serialization of evaluation results."""
        # Test EvaluationResult serialization
        eval_result = EvaluationResult(
            score=4.0,
            reasoning="Good response",
            confidence=0.8,
            metadata={"test": True},
        )

        serialized = batch_service._serialize_evaluation_result(eval_result)

        assert serialized["score"] == 4.0
        assert serialized["reasoning"] == "Good response"
        assert serialized["confidence"] == 0.8
        assert serialized["metadata"] == {"test": True}

        # Test dict serialization
        dict_result = {"winner": "A", "reasoning": "Better response"}
        serialized = batch_service._serialize_evaluation_result(dict_result)
        assert serialized == dict_result

        # Test other type serialization
        other_result = "Some string result"
        serialized = batch_service._serialize_evaluation_result(other_result)
        assert serialized == {"raw_result": "Some string result"}

    def test_progress_callback_management(self, batch_service):
        """Test progress callback management."""
        batch_id = "test-batch"

        def callback1(progress):
            pass

        def callback2(progress):
            pass

        # Add callbacks
        batch_service.add_progress_callback(batch_id, callback1)
        batch_service.add_progress_callback(batch_id, callback2)

        # Check callbacks are registered
        assert batch_id in batch_service._progress_callbacks
        assert len(batch_service._progress_callbacks[batch_id]) == 2

        # Remove callback
        batch_service.remove_progress_callback(batch_id, callback1)
        assert len(batch_service._progress_callbacks[batch_id]) == 1

        # Remove non-existent callback (should not raise error)
        batch_service.remove_progress_callback(batch_id, callback1)
        assert len(batch_service._progress_callbacks[batch_id]) == 1

    def test_get_batch_progress(self, batch_service):
        """Test getting batch progress."""
        batch_id = "test-batch"

        # Initially no progress
        progress = batch_service.get_batch_progress(batch_id)
        assert progress is None

        # Mock progress in batch service
        mock_progress = Mock(spec=BatchProgress)
        batch_service.batch_service._active_batches[batch_id] = mock_progress

        # Should return progress
        progress = batch_service.get_batch_progress(batch_id)
        assert progress == mock_progress

    def test_cancel_batch(self, batch_service):
        """Test batch cancellation."""
        batch_id = "test-batch"

        # Mock batch service
        batch_service.batch_service.cancel_batch = Mock(return_value=True)

        # Cancel batch
        cancelled = batch_service.cancel_batch(batch_id)
        assert cancelled

        # Verify method was called
        batch_service.batch_service.cancel_batch.assert_called_once_with(batch_id)

    def test_get_active_batches(self, batch_service):
        """Test getting active batches."""
        # Mock batch service
        mock_batches = ["batch1", "batch2"]
        batch_service.batch_service.get_active_batches = Mock(return_value=mock_batches)

        # Get active batches
        active = batch_service.get_active_batches()
        assert active == mock_batches

        # Verify method was called
        batch_service.batch_service.get_active_batches.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_sample_batch_file_jsonl(self, batch_service):
        """Test creating sample batch file in JSONL format."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            temp_file = f.name

        try:
            await batch_service.create_sample_batch_file(temp_file, format="jsonl")

            # Check that file was created
            assert Path(temp_file).exists()

            # Check file content
            with open(temp_file, "r") as f:
                lines = f.readlines()

            assert len(lines) == 2  # Two sample items

            # Parse first line
            first_item = json.loads(lines[0])
            assert first_item["type"] == "single"
            assert "prompt" in first_item
            assert "response" in first_item

            # Parse second line
            second_item = json.loads(lines[1])
            assert second_item["type"] == "comparison"
            assert "response_a" in second_item
            assert "response_b" in second_item

        finally:
            Path(temp_file).unlink()

    @pytest.mark.asyncio
    async def test_create_sample_batch_file_csv(self, batch_service):
        """Test creating sample batch file in CSV format."""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            temp_file = f.name

        try:
            await batch_service.create_sample_batch_file(temp_file, format="csv")

            # Check that file was created
            assert Path(temp_file).exists()

            # Check file content
            with open(temp_file, "r") as f:
                content = f.read()

            assert "type,prompt,response,model,criteria" in content
            assert "single," in content
            assert "comparison," in content

        finally:
            Path(temp_file).unlink()
