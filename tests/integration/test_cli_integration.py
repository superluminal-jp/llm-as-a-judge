"""Integration tests for CLI functionality."""

import pytest
import json
import tempfile
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock

from src.llm_judge.presentation.cli.main import main


class TestCLIIntegration:
    """Test CLI integration scenarios."""

    @pytest.mark.asyncio
    async def test_cli_evaluate_with_mock_judge(self):
        """Test CLI evaluation command with mocked LLM judge."""
        test_args = [
            "--output",
            "json",
            "evaluate",
            "What is artificial intelligence?",
            "AI is a field of computer science that aims to create intelligent machines.",
            "--criteria",
            "accuracy",
        ]

        # Mock multi-criteria evaluation result
        from src.llm_judge.domain.evaluation.results import (
            CriterionScore,
            MultiCriteriaResult,
        )

        mock_criteria_result = MultiCriteriaResult(
            criterion_scores=[
                CriterionScore("accuracy", 5, "Excellent accuracy", 0.9),
                CriterionScore("clarity", 4, "Good clarity", 0.8),
            ],
            judge_model="gpt-4",
        )

        with patch(
            "src.llm_judge.presentation.cli.main.LLMJudge"
        ) as mock_judge_class, patch("sys.argv", ["llm-judge"] + test_args):

            # Setup mock judge
            mock_judge = AsyncMock()
            mock_judge.evaluate_multi_criteria.return_value = mock_criteria_result
            mock_judge.judge_model = "gpt-4"
            mock_judge.close = AsyncMock()
            mock_judge_class.return_value = mock_judge

            # Capture stdout
            with patch("builtins.print") as mock_print:
                await main()

                # Verify the judge was used correctly
                mock_judge.evaluate_multi_criteria.assert_called_once()
                mock_judge.close.assert_called_once()

                # Check that JSON output was printed
                mock_print.assert_called()
                call_args = mock_print.call_args[0][0]
                assert '"type": "multi_criteria_evaluation"' in call_args

    @pytest.mark.asyncio
    async def test_cli_compare_with_mock_judge(self):
        """Test CLI comparison command with mocked LLM judge."""
        test_args = [
            "--output",
            "json",
            "compare",
            "Explain machine learning",
            "ML is a subset of AI",
            "Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed.",
            "--model-a",
            "gpt-3.5",
            "--model-b",
            "gpt-4",
        ]

        mock_result = {
            "winner": "B",
            "reasoning": "Response B provides more comprehensive explanation",
            "confidence": 0.9,
        }

        with patch(
            "src.llm_judge.presentation.cli.main.LLMJudge"
        ) as mock_judge_class, patch("sys.argv", ["llm-judge"] + test_args):

            mock_judge = AsyncMock()
            mock_judge.compare_responses.return_value = mock_result
            mock_judge.judge_model = "claude-3"
            mock_judge_class.return_value = mock_judge

            with patch("builtins.print") as mock_print:
                await main()

                mock_judge.compare_responses.assert_called_once()
                mock_judge.close.assert_called_once()

                # Check JSON output contains comparison data
                call_args = mock_print.call_args[0][0]
                assert '"type": "comparison"' in call_args
                assert '"winner": "B"' in call_args

    def test_cli_help_display(self):
        """Test CLI help display functionality."""
        with patch("sys.argv", ["llm-judge", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                with patch("builtins.print") as mock_print:
                    from src.llm_judge.presentation.cli.main import create_parser

                    parser = create_parser()
                    parser.parse_args(["--help"])

            # Help should exit with code 0
            assert exc_info.value.code == 0

    @pytest.mark.asyncio
    async def test_cli_with_config_file(self):
        """Test CLI with configuration file."""
        config_data = {
            "openai_api_key": "sk-test123",
            "default_provider": "openai",
            "openai_model": "gpt-5-2025-08-07",
            "request_timeout": 60,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)

        test_args = [
            "--config",
            str(config_path),
            "evaluate",
            "Test prompt",
            "Test response",
        ]

        try:
            with patch(
                "src.llm_judge.presentation.cli.main.LLMJudge"
            ) as mock_judge_class, patch("sys.argv", ["llm-judge"] + test_args):

                from src.llm_judge.domain.evaluation.results import (
                    CriterionScore,
                    MultiCriteriaResult,
                )

                mock_criteria_result = MultiCriteriaResult(
                    criterion_scores=[
                        CriterionScore("accuracy", 4, "Test evaluation", 0.7)
                    ],
                    judge_model="gpt-4",
                )

                mock_judge = AsyncMock()
                mock_judge.evaluate_multi_criteria.return_value = mock_criteria_result
                mock_judge.judge_model = "gpt-4"
                mock_judge.close = AsyncMock()
                mock_judge_class.return_value = mock_judge

                with patch("builtins.print"):
                    await main()

                # Verify judge was created with config
                mock_judge_class.assert_called_once()

        finally:
            config_path.unlink()

    def test_cli_error_handling(self):
        """Test CLI error handling for invalid arguments."""
        from src.llm_judge.presentation.cli.main import create_parser

        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["invalid-command"])

    @pytest.mark.asyncio
    async def test_cli_keyboard_interrupt(self):
        """Test CLI handling of keyboard interrupt."""
        test_args = ["evaluate", "prompt", "response"]

        with patch("src.llm_judge.presentation.cli.main.evaluate_command") as mock_eval:
            mock_eval.side_effect = KeyboardInterrupt()

            with patch("sys.argv", ["llm-judge"] + test_args), patch(
                "builtins.print"
            ) as mock_print, patch("sys.exit") as mock_exit:

                await main()

                mock_exit.assert_called_with(1)
                # Check that interrupted message was printed
                mock_print.assert_called()
                call_args = str(mock_print.call_args)
                assert "Interrupted by user" in call_args

    def test_cli_module_execution(self):
        """Test CLI execution as Python module."""
        # Test that the module can be imported and basic structure works
        from src.llm_judge.__main__ import main as module_main
        from src.llm_judge.presentation.cli import cli_entry

        # These should be callable (actual execution would require mocking)
        assert callable(module_main)
        assert callable(cli_entry)

    @pytest.mark.asyncio
    async def test_cli_text_output_formatting(self):
        """Test CLI text output formatting."""
        test_args = ["--output", "text", "evaluate", "Test question", "Test answer"]

        with patch(
            "src.llm_judge.presentation.cli.main.LLMJudge"
        ) as mock_judge_class, patch("sys.argv", ["llm-judge"] + test_args):

            from src.llm_judge.domain.evaluation.results import (
                CriterionScore,
                MultiCriteriaResult,
            )

            mock_criteria_result = MultiCriteriaResult(
                criterion_scores=[
                    CriterionScore("accuracy", 4, "Well structured response", 0.8)
                ],
                judge_model="claude-3",
            )

            mock_judge = AsyncMock()
            mock_judge.evaluate_multi_criteria.return_value = mock_criteria_result
            mock_judge.judge_model = "claude-3"
            mock_judge.close = AsyncMock()
            mock_judge_class.return_value = mock_judge

            with patch("builtins.print") as mock_print:
                await main()

                # Check that multi-criteria formatting was used
                call_args = mock_print.call_args[0][0]
                assert "Multi-Criteria LLM Evaluation Results" in call_args
                assert "accuracy" in call_args
                assert "Judge Model: claude-3" in call_args

    @pytest.mark.asyncio
    async def test_cli_provider_override(self):
        """Test CLI provider override functionality."""
        test_args = [
            "--provider",
            "anthropic",
            "--judge-model",
            "claude-3",
            "evaluate",
            "Test prompt",
            "Test response",
        ]

        with patch(
            "src.llm_judge.presentation.cli.main.load_cli_config"
        ) as mock_config, patch(
            "src.llm_judge.presentation.cli.main.LLMJudge"
        ) as mock_judge_class, patch(
            "sys.argv", ["llm-judge"] + test_args
        ):

            mock_config_obj = type(
                "LLMConfig",
                (),
                {
                    "custom_criteria": None,
                    "criteria_file": None,
                    "default_criteria_type": "balanced",
                    "criteria_weights": None,
                    "use_equal_weights": True,
                },
            )()
            mock_config.return_value = mock_config_obj

            from src.llm_judge.domain.evaluation.results import (
                CriterionScore,
                MultiCriteriaResult,
            )

            mock_criteria_result = MultiCriteriaResult(
                criterion_scores=[
                    CriterionScore("accuracy", 3, "Test evaluation", 0.6)
                ],
                judge_model="claude-3",
            )

            mock_judge = AsyncMock()
            mock_judge.evaluate_multi_criteria.return_value = mock_criteria_result
            mock_judge.judge_model = "claude-3"
            mock_judge.close = AsyncMock()
            mock_judge_class.return_value = mock_judge

            with patch("builtins.print"):
                await main()

            # Verify config was loaded with provider override
            mock_config.assert_called_once()
            call_args = mock_config.call_args
            assert call_args[0][1] == "anthropic"  # provider argument
            assert call_args[0][2] == "claude-3"  # judge_model argument
