"""
Integration tests for batch processing system.

Tests the complete batch processing workflow including file I/O,
CLI integration, and end-to-end batch evaluation processing.
"""

import pytest
import json
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from src.llm_judge.application.services.batch_service import BatchProcessingService
from src.llm_judge.application.services.llm_judge_service import (
    LLMJudge,
)
from src.llm_judge.domain.models import (
    CandidateResponse,
    EvaluationResult,
)
from src.llm_judge.domain.batch.models import (
    BatchRequest,
    BatchResult,
    BatchEvaluationItem,
)
from src.llm_judge.domain.batch.models import (
    BatchStatus,
    EvaluationType,
)
from src.llm_judge.domain.evaluation.results import (
    MultiCriteriaResult,
    AggregatedScore,
    CriterionScore,
)
from src.llm_judge.infrastructure.config.config import LLMConfig


class TestBatchProcessingIntegration:
    """Integration tests for batch processing system."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration for testing."""
        config = Mock(spec=LLMConfig)
        config.default_provider = "openai"
        config.openai_model = "gpt-3.5-turbo"
        config.persistence_enabled = False
        return config

    @pytest.fixture
    def mock_llm_judge(self, mock_config):
        """Create a mock LLM judge for testing."""
        judge = Mock(spec=LLMJudge)
        judge.config = mock_config

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
        return BatchProcessingService(llm_judge=mock_llm_judge, max_workers=3)

    @pytest.mark.asyncio
    async def test_end_to_end_batch_processing_jsonl(
        self, batch_service, mock_llm_judge
    ):
        """Test complete end-to-end batch processing with JSONL file."""
        # Create test data
        test_data = [
            {
                "type": "single",
                "prompt": "What is artificial intelligence?",
                "response": "AI is a field of computer science focused on creating intelligent machines.",
                "model": "gpt-3.5-turbo",
                "criteria": "accuracy and clarity",
            },
            {
                "type": "single",
                "prompt": "Explain machine learning",
                "response": "Machine learning is a subset of AI that enables computers to learn from data.",
                "model": "gpt-4",
                "criteria": "completeness and accuracy",
            },
            {
                "type": "comparison",
                "prompt": "What is deep learning?",
                "response_a": "Deep learning uses neural networks with multiple layers.",
                "response_b": "Deep learning is a subset of machine learning that uses artificial neural networks with multiple layers to model and understand complex patterns in data.",
                "model_a": "gpt-3.5-turbo",
                "model_b": "gpt-4",
            },
        ]

        # Create temporary JSONL file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for item in test_data:
                f.write(json.dumps(item) + "\n")
            input_file = f.name

        # Create temporary output file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            output_file = f.name

        try:
            # Process batch
            result = await batch_service.process_batch_from_file(
                file_path=input_file, output_path=output_file
            )

            # Verify processing results
            assert isinstance(result, BatchResult)
            assert result.status == BatchStatus.COMPLETED
            assert result.completed_items_count == 3
            assert result.failed_items_count == 0
            assert result.success_rate == 1.0

            # Verify LLM judge was called correctly
            assert (
                mock_llm_judge.evaluate_multi_criteria.call_count == 2
            )  # Two single evaluations
            assert mock_llm_judge.compare_responses.call_count == 1  # One comparison

            # Verify output file was created
            assert Path(output_file).exists()

            # Verify output file content
            with open(output_file, "r") as f:
                output_data = json.load(f)

            assert "batch_summary" in output_data
            assert "results" in output_data
            assert len(output_data["results"]) == 3

            # Check individual results
            for i, result_item in enumerate(output_data["results"]):
                assert result_item["status"] == "success"
                assert result_item["item_id"] is not None
                assert "processed_at" in result_item
                assert "processing_duration" in result_item

                if result_item["evaluation_type"] == "single":
                    assert "prompt" in result_item
                    assert "response" in result_item
                    assert "model" in result_item
                    assert "criteria" in result_item
                else:
                    assert "prompt" in result_item
                    assert "response_a" in result_item
                    assert "response_b" in result_item
                    assert "model_a" in result_item
                    assert "model_b" in result_item

        finally:
            Path(input_file).unlink()
            Path(output_file).unlink()

    @pytest.mark.asyncio
    async def test_end_to_end_batch_processing_csv(self, batch_service, mock_llm_judge):
        """Test complete end-to-end batch processing with CSV file."""
        # Create test CSV data
        csv_content = """type,prompt,response,model,criteria
single,"What is AI?","AI is artificial intelligence","gpt-3.5","accuracy"
single,"What is ML?","Machine learning is a subset of AI","gpt-4","clarity"
"""

        # Create temporary CSV file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            input_file = f.name

        try:
            # Process batch
            result = await batch_service.process_batch_from_file(input_file)

            # Verify processing results
            assert isinstance(result, BatchResult)
            assert result.status == BatchStatus.COMPLETED
            assert result.completed_items_count == 2
            assert result.failed_items_count == 0
            assert result.success_rate == 1.0

            # Verify LLM judge was called
            assert mock_llm_judge.evaluate_multi_criteria.call_count == 2

        finally:
            Path(input_file).unlink()

    @pytest.mark.asyncio
    async def test_end_to_end_batch_processing_json(
        self, batch_service, mock_llm_judge
    ):
        """Test complete end-to-end batch processing with JSON file."""
        # Create test JSON data
        json_data = {
            "items": [
                {
                    "type": "single",
                    "prompt": "What is AI?",
                    "response": "AI is artificial intelligence",
                    "model": "gpt-3.5",
                    "criteria": "accuracy",
                },
                {
                    "type": "single",
                    "prompt": "What is ML?",
                    "response": "Machine learning is a subset of AI",
                    "model": "gpt-4",
                    "criteria": "clarity",
                },
            ]
        }

        # Create temporary JSON file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_data, f)
            input_file = f.name

        try:
            # Process batch
            result = await batch_service.process_batch_from_file(input_file)

            # Verify processing results
            assert isinstance(result, BatchResult)
            assert result.status == BatchStatus.COMPLETED
            assert result.completed_items_count == 2
            assert result.failed_items_count == 0
            assert result.success_rate == 1.0

        finally:
            Path(input_file).unlink()

    @pytest.mark.asyncio
    async def test_batch_processing_with_mixed_success_failure(
        self, batch_service, mock_llm_judge
    ):
        """Test batch processing with mixed success and failure scenarios."""
        # Mock some evaluations to fail
        call_count = 0

        async def mock_evaluate_multi_criteria(candidate):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Second call fails consistently
                raise Exception("Simulated evaluation failure")

            # Return successful result
            mock_multi_result = Mock(spec=MultiCriteriaResult)
            mock_multi_result.aggregated = Mock(spec=AggregatedScore)
            mock_multi_result.aggregated.overall_score = 4.0
            mock_multi_result.aggregated.confidence = 0.8
            mock_multi_result.overall_reasoning = "Good evaluation"
            mock_multi_result.criterion_scores = []
            return mock_multi_result

        mock_llm_judge.evaluate_multi_criteria = mock_evaluate_multi_criteria

        # Create test data
        test_data = [
            {
                "type": "single",
                "prompt": "What is AI?",
                "response": "AI is artificial intelligence",
                "model": "gpt-3.5",
                "criteria": "accuracy",
            },
            {
                "type": "single",
                "prompt": "What is ML?",
                "response": "ML is machine learning",
                "model": "gpt-4",
                "criteria": "clarity",
            },
            {
                "type": "single",
                "prompt": "What is DL?",
                "response": "DL is deep learning",
                "model": "gpt-3.5",
                "criteria": "completeness",
            },
        ]

        # Create temporary JSONL file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for item in test_data:
                f.write(json.dumps(item) + "\n")
            input_file = f.name

        try:
            # Process batch with retries disabled to ensure failure
            result = await batch_service.process_batch_from_file(
                input_file, batch_config={"retry_failed_items": False}
            )

            # Verify processing results
            assert isinstance(result, BatchResult)
            assert result.status == BatchStatus.COMPLETED
            assert result.completed_items_count == 2  # Two successful
            assert result.failed_items_count == 1  # One failed
            assert result.success_rate == 2 / 3  # 2 out of 3 successful

            # Verify failed item has error
            failed_item = result.failed_items[0]
            assert failed_item.error is not None
            assert "Simulated evaluation failure" in failed_item.error

        finally:
            Path(input_file).unlink()

    @pytest.mark.asyncio
    async def test_batch_processing_with_retries(self, batch_service, mock_llm_judge):
        """Test batch processing with retry logic."""
        # Mock evaluation to fail first few times then succeed
        call_count = 0

        async def mock_evaluate_multi_criteria(candidate):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # Fail first 2 times
                raise Exception("Temporary failure")

            # Return successful result
            mock_multi_result = Mock(spec=MultiCriteriaResult)
            mock_multi_result.aggregated = Mock(spec=AggregatedScore)
            mock_multi_result.aggregated.overall_score = 4.0
            mock_multi_result.aggregated.confidence = 0.8
            mock_multi_result.overall_reasoning = "Good evaluation after retry"
            mock_multi_result.criterion_scores = []
            return mock_multi_result

        mock_llm_judge.evaluate_multi_criteria = mock_evaluate_multi_criteria

        # Create test data
        test_data = [
            {
                "type": "single",
                "prompt": "What is AI?",
                "response": "AI is artificial intelligence",
                "model": "gpt-3.5",
                "criteria": "accuracy",
            }
        ]

        # Create temporary JSONL file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for item in test_data:
                f.write(json.dumps(item) + "\n")
            input_file = f.name

        try:
            # Process batch with retries enabled
            result = await batch_service.process_batch_from_file(
                file_path=input_file, batch_config={"max_retries_per_item": 3}
            )

            # Verify processing results
            assert isinstance(result, BatchResult)
            assert result.status == BatchStatus.COMPLETED
            assert result.completed_items_count == 1
            assert result.failed_items_count == 0
            assert result.success_rate == 1.0

            # Verify retries were attempted (3 calls total: 1 initial + 2 retries)
            assert call_count == 3

        finally:
            Path(input_file).unlink()

    @pytest.mark.asyncio
    async def test_batch_processing_with_custom_configuration(
        self, batch_service, mock_llm_judge
    ):
        """Test batch processing with custom configuration."""
        # Create test data
        test_data = [
            {
                "type": "single",
                "prompt": "What is AI?",
                "response": "AI is artificial intelligence",
                "model": "gpt-3.5",
                "criteria": "accuracy",
            },
            {
                "type": "single",
                "prompt": "What is ML?",
                "response": "ML is machine learning",
                "model": "gpt-4",
                "criteria": "clarity",
            },
        ]

        # Create temporary JSONL file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for item in test_data:
                f.write(json.dumps(item) + "\n")
            input_file = f.name

        # Custom batch configuration
        batch_config = {
            "name": "Custom Test Batch",
            "description": "Integration test batch",
            "max_concurrent_items": 1,  # Sequential processing
            "retry_failed_items": False,
            "max_retries_per_item": 0,
            "continue_on_error": True,
            "judge_provider": "openai",
            "judge_model": "gpt-4",
            "metadata": {"test": True, "environment": "integration"},
        }

        try:
            # Process batch with custom configuration
            result = await batch_service.process_batch_from_file(
                file_path=input_file, batch_config=batch_config
            )

            # Verify processing results
            assert isinstance(result, BatchResult)
            assert result.status == BatchStatus.COMPLETED
            assert result.completed_items_count == 2
            assert result.failed_items_count == 0

            # Verify custom configuration was applied
            assert result.batch_request.name == "Custom Test Batch"
            assert result.batch_request.description == "Integration test batch"
            assert result.batch_request.max_concurrent_items == 1
            assert result.batch_request.retry_failed_items is False
            assert result.batch_request.max_retries_per_item == 0
            assert result.batch_request.continue_on_error is True
            assert result.batch_request.judge_provider == "openai"
            assert result.batch_request.judge_model == "gpt-4"
            assert result.batch_request.metadata == {
                "test": True,
                "environment": "integration",
            }

        finally:
            Path(input_file).unlink()

    @pytest.mark.asyncio
    async def test_batch_processing_with_progress_tracking(
        self, batch_service, mock_llm_judge
    ):
        """Test batch processing with progress tracking."""
        # Create test data
        test_data = [
            {
                "type": "single",
                "prompt": "What is AI?",
                "response": "AI is artificial intelligence",
                "model": "gpt-3.5",
                "criteria": "accuracy",
            },
            {
                "type": "single",
                "prompt": "What is ML?",
                "response": "ML is machine learning",
                "model": "gpt-4",
                "criteria": "clarity",
            },
            {
                "type": "single",
                "prompt": "What is DL?",
                "response": "DL is deep learning",
                "model": "gpt-3.5",
                "criteria": "completeness",
            },
        ]

        # Create temporary JSONL file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for item in test_data:
                f.write(json.dumps(item) + "\n")
            input_file = f.name

        # Track progress updates
        progress_updates = []

        def progress_callback(progress):
            progress_updates.append(
                {
                    "batch_id": progress.batch_id,
                    "total_items": progress.total_items,
                    "processing_items": progress.processing_items,
                    "completed_items": progress.completed_items,
                    "failed_items": progress.failed_items,
                    "pending_items": progress.pending_items,
                    "items_per_second": progress.items_per_second,
                }
            )

        try:
            # Process batch with progress tracking
            result = await batch_service.process_batch_from_file(
                file_path=input_file, progress_callback=progress_callback
            )

            # Verify processing results
            assert isinstance(result, BatchResult)
            assert result.status == BatchStatus.COMPLETED
            assert result.completed_items_count == 3

            # Verify progress updates were received
            assert len(progress_updates) > 0

            # Check final progress state
            final_progress = progress_updates[-1]
            assert final_progress["total_items"] == 3
            assert final_progress["completed_items"] == 3
            assert final_progress["failed_items"] == 0
            assert final_progress["pending_items"] == 0
            assert final_progress["processing_items"] == 0

            # Verify progress progression
            for i, progress in enumerate(progress_updates):
                assert progress["total_items"] == 3
                assert (
                    progress["completed_items"]
                    + progress["failed_items"]
                    + progress["pending_items"]
                    + progress["processing_items"]
                    == 3
                )

        finally:
            Path(input_file).unlink()

    @pytest.mark.asyncio
    async def test_batch_processing_performance_metrics(
        self, batch_service, mock_llm_judge
    ):
        """Test batch processing performance metrics."""
        # Create test data
        test_data = [
            {
                "type": "single",
                "prompt": f"What is AI concept {i}?",
                "response": f"AI concept {i} is about artificial intelligence",
                "model": "gpt-3.5",
                "criteria": "accuracy",
            }
            for i in range(5)
        ]

        # Create temporary JSONL file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for item in test_data:
                f.write(json.dumps(item) + "\n")
            input_file = f.name

        try:
            # Process batch
            result = await batch_service.process_batch_from_file(input_file)

            # Verify processing results
            assert isinstance(result, BatchResult)
            assert result.status == BatchStatus.COMPLETED
            assert result.completed_items_count == 5
            assert result.failed_items_count == 0

            # Verify performance metrics
            assert result.processing_duration > 0
            assert result.average_processing_time is not None
            assert result.average_processing_time > 0

            # Verify individual item processing times
            for item in result.successful_items:
                assert item.processing_duration is not None
                assert item.processing_duration > 0
                assert item.processed_at is not None

        finally:
            Path(input_file).unlink()

    @pytest.mark.asyncio
    async def test_batch_processing_error_handling(self, batch_service, mock_llm_judge):
        """Test batch processing error handling scenarios."""
        # Test with invalid file format
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            temp_file = f.name

        try:
            with pytest.raises(ValueError, match="Unsupported file format"):
                await batch_service.process_batch_from_file(temp_file)
        finally:
            Path(temp_file).unlink()

        # Test with nonexistent file
        with pytest.raises(FileNotFoundError, match="Batch file not found"):
            await batch_service.process_batch_from_file("nonexistent.jsonl")

        # Test with malformed JSON
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"invalid": json}\n')  # Invalid JSON
            f.write(
                '{"type": "single", "prompt": "What is AI?", "response": "AI is artificial intelligence"}\n'
            )
            temp_file = f.name

        try:
            # Should process valid lines and skip invalid ones
            result = await batch_service.process_batch_from_file(temp_file)
            assert isinstance(result, BatchResult)
            assert result.status == BatchStatus.COMPLETED
            assert result.completed_items_count == 1  # Only valid line processed
        finally:
            Path(temp_file).unlink()
