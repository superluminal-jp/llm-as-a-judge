"""Tests for the Lambda handler (src/handler.py).

Covers:
- Successful evaluation with default (balanced) criteria via Anthropic.
- Input validation: missing/empty fields, invalid provider, invalid S3 URI.
- Provider error propagation.
- Default provider resolution from environment variables.
- Multi-provider selection (OpenAI, Bedrock) — US2.
- S3 criteria loading integration — US2.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.handler import (
    ConfigurationError,
    CriteriaLoadError,
    ProviderError,
    ValidationError,
    lambda_handler,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(**kwargs) -> dict:
    base = {
        "prompt": "Explain machine learning.",
        "response": "Machine learning uses statistical methods to learn from data.",
    }
    base.update(kwargs)
    return base


def _valid_eval_result(provider: str = "anthropic", model: str = "claude-sonnet-4-6") -> dict:
    """Return a minimal valid evaluation result dict (matches lambda-response schema).

    Parallel-only evaluation returns criterion_scores and reasoning (総評);
    no overall_score is computed.
    """
    return {
        "criterion_scores": {
            "accuracy": 4.0,
            "clarity": 4.0,
            "helpfulness": 4.0,
            "completeness": 4.0,
        },
        "reasoning": "総評: 各クライテリアの評価結果は以下のとおりである。",
        "judge_model": model,
        "provider": provider,
    }


# ---------------------------------------------------------------------------
# US1: Basic evaluation with Anthropic + default criteria
# ---------------------------------------------------------------------------


class TestBasicEvaluation:
    def test_basic_evaluation_success(
        self, sample_event, lambda_context, env_anthropic, monkeypatch
    ):
        """AC1: Handler returns a result matching the lambda-response.json schema."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        expected = _valid_eval_result()

        # Reset the config cache so monkeypatched env vars are picked up.
        import src.config as cfg_mod

        cfg_mod._config = None

        with patch("src.handler.get_provider") as mock_get_provider, patch(
            "src.handler.evaluate", return_value=expected
        ):
            mock_provider = MagicMock()
            mock_get_provider.return_value = mock_provider

            result = lambda_handler(sample_event, lambda_context)

        assert "criterion_scores" in result
        assert "reasoning" in result
        assert result["provider"] == "anthropic"

    def test_default_provider_used_when_not_specified(
        self, sample_event, lambda_context, monkeypatch
    ):
        """Handler uses DEFAULT_PROVIDER env var when event omits 'provider'."""
        monkeypatch.setenv("DEFAULT_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

        import src.config as cfg_mod

        cfg_mod._config = None

        expected = _valid_eval_result()

        with patch("src.handler.get_provider") as mock_get_provider, patch(
            "src.handler.evaluate", return_value=expected
        ):
            mock_get_provider.return_value = MagicMock()
            result = lambda_handler(sample_event, lambda_context)

        mock_get_provider.assert_called_once_with("anthropic", cfg_mod._config)
        assert result["provider"] == "anthropic"


# ---------------------------------------------------------------------------
# Input validation (AC5)
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_missing_prompt_raises_validation_error(self, lambda_context):
        """AC5: Missing 'prompt' field raises ValidationError."""
        event = {"response": "Some answer."}
        with pytest.raises(ValidationError, match="prompt"):
            lambda_handler(event, lambda_context)

    def test_empty_prompt_raises_validation_error(self, lambda_context):
        """AC5: Empty 'prompt' string raises ValidationError."""
        event = {"prompt": "   ", "response": "Some answer."}
        with pytest.raises(ValidationError, match="prompt"):
            lambda_handler(event, lambda_context)

    def test_missing_response_raises_validation_error(self, lambda_context):
        """AC5: Missing 'response' field raises ValidationError."""
        event = {"prompt": "What is AI?"}
        with pytest.raises(ValidationError, match="response"):
            lambda_handler(event, lambda_context)

    def test_empty_response_raises_validation_error(self, lambda_context):
        """AC5: Empty 'response' string raises ValidationError."""
        event = {"prompt": "What is AI?", "response": ""}
        with pytest.raises(ValidationError, match="response"):
            lambda_handler(event, lambda_context)

    def test_invalid_provider_raises_validation_error(self, lambda_context):
        """Unrecognised provider name raises ValidationError."""
        event = _make_event(provider="gpt-99")
        with pytest.raises(ValidationError, match="provider"):
            lambda_handler(event, lambda_context)

    def test_invalid_s3_uri_raises_validation_error(self, lambda_context):
        """Non-S3 URI in criteria_file raises ValidationError."""
        event = _make_event(criteria_file="http://not-s3/file.json")
        with pytest.raises(ValidationError, match="criteria_file"):
            lambda_handler(event, lambda_context)


# ---------------------------------------------------------------------------
# Provider error propagation (AC6)
# ---------------------------------------------------------------------------


class TestProviderErrorPropagation:
    def test_provider_error_propagates(
        self, sample_event, lambda_context, monkeypatch
    ):
        """AC6: ProviderError from evaluate() is re-raised unchanged."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("DEFAULT_PROVIDER", "anthropic")

        import src.config as cfg_mod

        cfg_mod._config = None

        with patch("src.handler.get_provider") as mock_get_provider, patch(
            "src.handler.evaluate", side_effect=ProviderError("API timeout")
        ):
            mock_get_provider.return_value = MagicMock()

            with pytest.raises(ProviderError, match="API timeout"):
                lambda_handler(sample_event, lambda_context)

    def test_missing_api_key_raises_configuration_error(
        self, sample_event, lambda_context, monkeypatch
    ):
        """ConfigurationError raised when API key env var is absent."""
        monkeypatch.setenv("DEFAULT_PROVIDER", "anthropic")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        import src.config as cfg_mod

        cfg_mod._config = None

        with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
            lambda_handler(sample_event, lambda_context)


# ---------------------------------------------------------------------------
# US2: Multi-provider selection
# ---------------------------------------------------------------------------


class TestMultiProviderSelection:
    def test_openai_provider_selected(
        self, sample_event, lambda_context, monkeypatch
    ):
        """Provider='openai' in event routes to OpenAI client."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")

        import src.config as cfg_mod

        cfg_mod._config = None

        event = {**sample_event, "provider": "openai"}
        expected = _valid_eval_result(provider="openai", model="gpt-4o")

        with patch("src.handler.get_provider") as mock_get_provider, patch(
            "src.handler.evaluate", return_value=expected
        ):
            mock_get_provider.return_value = MagicMock()
            result = lambda_handler(event, lambda_context)

        mock_get_provider.assert_called_once()
        assert mock_get_provider.call_args[0][0] == "openai"
        assert result["provider"] == "openai"

    def test_bedrock_provider_selected(
        self, sample_event, lambda_context, monkeypatch
    ):
        """Provider='bedrock' in event routes to Bedrock client."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        import src.config as cfg_mod

        cfg_mod._config = None

        event = {**sample_event, "provider": "bedrock"}
        expected = _valid_eval_result(
            provider="bedrock", model="anthropic.claude-sonnet-4-6"
        )

        with patch("src.handler.get_provider") as mock_get_provider, patch(
            "src.handler.evaluate", return_value=expected
        ):
            mock_get_provider.return_value = MagicMock()
            result = lambda_handler(event, lambda_context)

        mock_get_provider.assert_called_once()
        assert mock_get_provider.call_args[0][0] == "bedrock"


# ---------------------------------------------------------------------------
# US2: S3 criteria loading
# ---------------------------------------------------------------------------


class TestS3CriteriaLoading:
    def test_criteria_loaded_from_s3(
        self, sample_event, lambda_context, monkeypatch
    ):
        """When criteria_file is provided, load_from_s3 is called."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("DEFAULT_PROVIDER", "anthropic")

        import src.config as cfg_mod

        cfg_mod._config = None

        from src.criteria import EvaluationCriteria, CriterionDefinition

        mock_criteria = EvaluationCriteria(
            name="Custom",
            criteria=[
                CriterionDefinition(name="accuracy", description="Factual accuracy.")
            ],
        )
        event = {**sample_event, "criteria_file": "s3://my-bucket/criteria.json"}
        expected = _valid_eval_result()

        with patch("src.handler.load_from_s3", return_value=mock_criteria) as mock_s3, patch(
            "src.handler.get_provider"
        ) as mock_get_provider, patch("src.handler.evaluate", return_value=expected):
            mock_get_provider.return_value = MagicMock()
            lambda_handler(event, lambda_context)

        mock_s3.assert_called_once_with("s3://my-bucket/criteria.json")

    def test_s3_load_failure_raises_criteria_load_error(
        self, sample_event, lambda_context, monkeypatch
    ):
        """CriteriaLoadError from load_from_s3 propagates unchanged."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("DEFAULT_PROVIDER", "anthropic")

        import src.config as cfg_mod

        cfg_mod._config = None

        event = {**sample_event, "criteria_file": "s3://my-bucket/missing.json"}

        with patch(
            "src.handler.load_from_s3",
            side_effect=CriteriaLoadError("Not found"),
        ), patch("src.handler.get_provider"):
            with pytest.raises(CriteriaLoadError, match="Not found"):
                lambda_handler(event, lambda_context)
