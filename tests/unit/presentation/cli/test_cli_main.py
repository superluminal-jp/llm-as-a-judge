"""Unit tests for CLI main functionality."""

import pytest
import json
import argparse
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
import tempfile

from src.llm_judge.presentation.cli.main import (
    create_parser,
    load_cli_config,
    evaluate_command,
    compare_command,
    format_evaluation_output,
    format_comparison_output,
    CLIError,
)
from src.llm_judge.application.services.llm_judge_service import (
    EvaluationResult,
    CandidateResponse,
)
from src.llm_judge.infrastructure.config.config import LLMConfig


class TestCLIParser:
    """Test CLI argument parsing."""

    def test_create_parser_basic(self):
        """Test basic parser creation."""
        parser = create_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "llm-judge"

    def test_parser_global_options(self):
        """Test global command line options."""
        parser = create_parser()

        # Test provider option
        args = parser.parse_args(
            ["--provider", "openai", "evaluate", "prompt", "response"]
        )
        assert args.provider == "openai"

        # Test judge model option
        args = parser.parse_args(
            ["--judge-model", "gpt-4", "evaluate", "prompt", "response"]
        )
        assert args.judge_model == "gpt-4"

        # Test output format
        args = parser.parse_args(["--output", "json", "evaluate", "prompt", "response"])
        assert args.output == "json"

    def test_evaluate_command_parsing(self):
        """Test evaluate command argument parsing."""
        parser = create_parser()

        args = parser.parse_args(["evaluate", "test prompt", "test response"])
        assert args.command == "evaluate"
        assert args.prompt == "test prompt"
        assert args.response == "test response"
        assert args.criteria == "overall quality"  # default

        # Test with criteria
        args = parser.parse_args(
            ["evaluate", "prompt", "response", "--criteria", "accuracy"]
        )
        assert args.criteria == "accuracy"

        # Test with model
        args = parser.parse_args(["evaluate", "prompt", "response", "--model", "gpt-4"])
        assert args.model == "gpt-4"

    def test_compare_command_parsing(self):
        """Test compare command argument parsing."""
        parser = create_parser()

        args = parser.parse_args(["compare", "test prompt", "response A", "response B"])
        assert args.command == "compare"
        assert args.prompt == "test prompt"
        assert args.response_a == "response A"
        assert args.response_b == "response B"

        # Test with model options
        args = parser.parse_args(
            [
                "compare",
                "prompt",
                "resp_a",
                "resp_b",
                "--model-a",
                "gpt-4",
                "--model-b",
                "claude-3",
            ]
        )
        assert args.model_a == "gpt-4"
        assert args.model_b == "claude-3"


class TestConfigLoading:
    """Test CLI configuration loading."""

    def test_load_cli_config_default(self):
        """Test loading default configuration."""
        with patch("src.llm_judge.presentation.cli.main.load_config") as mock_load:
            mock_config = Mock(spec=LLMConfig)
            mock_load.return_value = mock_config

            result = load_cli_config(None, None, None)
            assert result == mock_config
            mock_load.assert_called_once()

    def test_load_cli_config_with_overrides(self):
        """Test loading configuration with CLI overrides."""
        with patch("src.llm_judge.presentation.cli.main.load_config") as mock_load:
            mock_config = Mock(spec=LLMConfig)
            mock_load.return_value = mock_config

            result = load_cli_config(None, "anthropic", "claude-3")
            assert result.default_provider == "anthropic"

    def test_load_cli_config_from_file(self):
        """Test loading configuration from file."""
        config_data = {
            "openai_api_key": "test-key",
            "default_provider": "openai",
            "request_timeout": 30,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)

        try:
            result = load_cli_config(config_path, None, None)
            assert result.openai_api_key == "test-key"
            assert result.default_provider == "openai"
        finally:
            config_path.unlink()

    def test_load_cli_config_file_not_found(self):
        """Test error handling for missing config file."""
        non_existent_path = Path("/non/existent/config.json")

        with pytest.raises(CLIError, match="Configuration file not found"):
            load_cli_config(non_existent_path, None, None)

    def test_load_cli_config_invalid_json(self):
        """Test error handling for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json content")
            config_path = Path(f.name)

        try:
            with pytest.raises(CLIError, match="Error loading configuration"):
                load_cli_config(config_path, None, None)
        finally:
            config_path.unlink()


class TestEvaluateCommand:
    """Test evaluate command execution."""

    @pytest.mark.asyncio
    async def test_evaluate_command_success(self):
        """Test successful evaluation command execution."""
        # Mock arguments
        args = Mock()
        args.config = None
        args.provider = "openai"
        args.judge_model = "gpt-4"
        args.prompt = "Test prompt"
        args.response = "Test response"
        args.model = "gpt-3.5"
        args.criteria = "accuracy"
        args.list_criteria_types = False
        args.custom_criteria = None
        args.criteria_file = None
        args.criteria_weights = None
        args.use_equal_weights = True

        # Mock LLMJudge
        mock_judge = AsyncMock()
        # Create mock multi-criteria result
        from src.llm_judge.domain.evaluation.results import (
            MultiCriteriaResult,
            CriterionScore,
            AggregatedScore,
        )

        mock_criterion_score = CriterionScore(
            criterion_name="accuracy", score=4, reasoning="Good accuracy"
        )
        mock_aggregated = AggregatedScore(
            overall_score=4.5,
            weighted_score=4.5,
            confidence=0.85,
            min_score=4,
            max_score=5,
        )
        mock_multi_result = MultiCriteriaResult(
            criterion_scores=[mock_criterion_score], aggregated=mock_aggregated
        )
        mock_judge.evaluate_multi_criteria.return_value = mock_multi_result
        mock_judge.judge_model = "gpt-4"

        with patch(
            "src.llm_judge.presentation.cli.main.load_cli_config"
        ) as mock_config, patch(
            "src.llm_judge.presentation.cli.main.LLMJudge"
        ) as mock_judge_class:

            mock_config_obj = Mock()
            mock_config_obj.custom_criteria = None
            mock_config_obj.criteria_file = None
            mock_config_obj.default_criteria_type = "comprehensive"
            mock_config_obj.criteria_weights = None
            mock_config_obj.use_equal_weights = True
            # Configure the mock to return actual values instead of Mock objects
            mock_config_obj.configure_mock(
                **{
                    "custom_criteria": None,
                    "criteria_file": None,
                    "default_criteria_type": "comprehensive",
                    "criteria_weights": None,
                    "use_equal_weights": True,
                }
            )
            mock_config.return_value = mock_config_obj
            mock_judge_class.return_value = mock_judge

            result = await evaluate_command(args)

            assert result["type"] == "multi_criteria_evaluation"
            assert "multi_criteria_result" in result
            assert result["prompt"] == "Test prompt"
            assert result["response"] == "Test response"
            assert result["judge_model"] == "gpt-4"
            # Verify multi-criteria result structure
            multi_result = result["multi_criteria_result"]
            assert multi_result.aggregated.overall_score == 4.5
            assert len(multi_result.criterion_scores) == 1
            assert multi_result.criterion_scores[0].score == 4

            mock_judge.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_command_with_defaults(self):
        """Test evaluate command with default values."""
        args = Mock()
        args.config = None
        args.provider = None
        args.judge_model = None
        args.prompt = "Test prompt"
        args.response = "Test response"
        args.model = None
        args.criteria = "overall quality"
        args.list_criteria_types = False
        args.custom_criteria = None
        args.criteria_file = None
        args.criteria_weights = None
        args.use_equal_weights = True

        mock_judge = AsyncMock()
        # Create mock multi-criteria result
        from src.llm_judge.domain.evaluation.results import (
            MultiCriteriaResult,
            CriterionScore,
            AggregatedScore,
        )

        mock_criterion_score = CriterionScore(
            criterion_name="overall quality", score=3, reasoning="Average"
        )
        mock_aggregated = AggregatedScore(
            overall_score=3.0,
            weighted_score=3.0,
            confidence=0.7,
            min_score=3,
            max_score=3,
        )
        mock_multi_result = MultiCriteriaResult(
            criterion_scores=[mock_criterion_score], aggregated=mock_aggregated
        )
        mock_judge.evaluate_multi_criteria.return_value = mock_multi_result
        mock_judge.judge_model = "claude-3"

        with patch(
            "src.llm_judge.presentation.cli.main.load_cli_config"
        ) as mock_config, patch(
            "src.llm_judge.presentation.cli.main.LLMJudge"
        ) as mock_judge_class:

            mock_config_obj = Mock()
            mock_config_obj.custom_criteria = None
            mock_config_obj.criteria_file = None
            mock_config_obj.default_criteria_type = "comprehensive"
            mock_config_obj.criteria_weights = None
            mock_config_obj.use_equal_weights = True
            # Configure the mock to return actual values instead of Mock objects
            mock_config_obj.configure_mock(
                **{
                    "custom_criteria": None,
                    "criteria_file": None,
                    "default_criteria_type": "comprehensive",
                    "criteria_weights": None,
                    "use_equal_weights": True,
                }
            )
            mock_config.return_value = mock_config_obj
            mock_judge_class.return_value = mock_judge

            result = await evaluate_command(args)

            assert result["model"] == "unknown"  # default when None provided
            assert result["type"] == "multi_criteria_evaluation"
            # Check that the criteria is reflected in the multi-criteria result
            multi_result = result["multi_criteria_result"]
            assert multi_result.criterion_scores[0].criterion_name == "overall quality"


class TestCompareCommand:
    """Test compare command execution."""

    @pytest.mark.asyncio
    async def test_compare_command_success(self):
        """Test successful comparison command execution."""
        args = Mock()
        args.config = None
        args.provider = "anthropic"
        args.judge_model = "claude-3"
        args.prompt = "Test prompt"
        args.response_a = "Response A"
        args.response_b = "Response B"
        args.model_a = "gpt-4"
        args.model_b = "claude-3"

        mock_judge = AsyncMock()
        mock_result = {
            "winner": "B",
            "reasoning": "Response B is more comprehensive",
            "confidence": 0.9,
        }
        mock_judge.compare_responses.return_value = mock_result
        mock_judge.judge_model = "claude-3"

        with patch(
            "src.llm_judge.presentation.cli.main.load_cli_config"
        ) as mock_config, patch(
            "src.llm_judge.presentation.cli.main.LLMJudge"
        ) as mock_judge_class:

            mock_config.return_value = Mock()
            mock_judge_class.return_value = mock_judge

            result = await compare_command(args)

            assert result["type"] == "comparison"
            assert result["winner"] == "B"
            assert result["reasoning"] == "Response B is more comprehensive"
            assert result["confidence"] == 0.9
            assert result["judge_model"] == "claude-3"

            mock_judge.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_compare_command_tie_result(self):
        """Test comparison command with tie result."""
        args = Mock()
        args.config = None
        args.provider = None
        args.judge_model = None
        args.prompt = "Test prompt"
        args.response_a = "Response A"
        args.response_b = "Response B"
        args.model_a = None
        args.model_b = None

        mock_judge = AsyncMock()
        mock_result = {
            "winner": "tie",
            "reasoning": "Both responses are equally good",
            "confidence": 0.6,
        }
        mock_judge.compare_responses.return_value = mock_result
        mock_judge.judge_model = "gpt-4"

        with patch(
            "src.llm_judge.presentation.cli.main.load_cli_config"
        ) as mock_config, patch(
            "src.llm_judge.presentation.cli.main.LLMJudge"
        ) as mock_judge_class:

            mock_config.return_value = Mock()
            mock_judge_class.return_value = mock_judge

            result = await compare_command(args)

            assert result["winner"] == "tie"
            assert result["model_a"] == "unknown"
            assert result["model_b"] == "unknown"


class TestOutputFormatting:
    """Test output formatting functions."""

    def test_format_evaluation_output_text(self):
        """Test text formatting for evaluation results."""
        result = {
            "type": "evaluation",
            "prompt": "What is AI?",
            "response": "AI is artificial intelligence",
            "model": "gpt-4",
            "criteria": "accuracy",
            "score": 4.5,
            "reasoning": "Good explanation",
            "confidence": 0.85,
            "judge_model": "claude-3",
        }

        output = format_evaluation_output(result, "text")

        assert "LLM-as-a-Judge Evaluation" in output
        assert "Judge Model: claude-3" in output
        assert "Score: 4.5/5" in output
        assert "Confidence: 0.85" in output
        assert "Good explanation" in output

    def test_format_evaluation_output_json(self):
        """Test JSON formatting for evaluation results."""
        result = {"type": "evaluation", "score": 4.5, "reasoning": "Good explanation"}

        output = format_evaluation_output(result, "json")
        parsed = json.loads(output)

        assert parsed["type"] == "evaluation"
        assert parsed["score"] == 4.5

    def test_format_comparison_output_text(self):
        """Test text formatting for comparison results."""
        result = {
            "type": "comparison",
            "prompt": "Explain ML",
            "response_a": "Basic explanation",
            "response_b": "Detailed explanation",
            "model_a": "gpt-3.5",
            "model_b": "gpt-4",
            "winner": "B",
            "reasoning": "Response B is more comprehensive",
            "confidence": 0.9,
            "judge_model": "claude-3",
        }

        output = format_comparison_output(result, "text")

        assert "LLM-as-a-Judge Comparison" in output
        assert "Winner: Response B" in output
        assert "Confidence: 0.90" in output
        assert "Response B is more comprehensive" in output

    def test_format_comparison_output_tie(self):
        """Test text formatting for tie comparison results."""
        result = {
            "type": "comparison",
            "prompt": "Test",
            "response_a": "A",
            "response_b": "B",
            "model_a": "model1",
            "model_b": "model2",
            "winner": "tie",
            "reasoning": "Equal quality",
            "confidence": 0.5,
            "judge_model": "judge",
        }

        output = format_comparison_output(result, "text")
        assert "Result: TIE" in output

    def test_format_comparison_output_json(self):
        """Test JSON formatting for comparison results."""
        result = {"type": "comparison", "winner": "A", "confidence": 0.8}

        output = format_comparison_output(result, "json")
        parsed = json.loads(output)

        assert parsed["type"] == "comparison"
        assert parsed["winner"] == "A"
