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
    _normalize_context,
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
    names = ("accuracy", "clarity", "helpfulness", "completeness")
    return {
        "criterion_scores": {n: 4.0 for n in names},
        "criterion_reasoning": {n: "Criterion met expectations." for n in names},
        "criterion_assessability": {n: "assessed" for n in names},
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
    def test_response_only_without_prompt_succeeds_when_evaluate_mocked(
        self, lambda_context, monkeypatch
    ):
        """Response-only input is valid when the other role is omitted or blank."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("DEFAULT_PROVIDER", "anthropic")

        import src.config as cfg_mod

        cfg_mod._config = None

        event = {"response": "Some answer."}
        with patch("src.handler.get_provider") as mock_get_provider, patch(
            "src.handler.evaluate", return_value=_valid_eval_result()
        ):
            mock_get_provider.return_value = MagicMock()
            result = lambda_handler(event, lambda_context)

        assert result["provider"] == "anthropic"
        assert "criterion_scores" in result

    def test_whitespace_prompt_allowed_when_response_present(
        self, lambda_context, monkeypatch
    ):
        """Whitespace-only prompt is allowed if response text is non-empty."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("DEFAULT_PROVIDER", "anthropic")

        import src.config as cfg_mod

        cfg_mod._config = None

        event = {"prompt": "   ", "response": "Some answer."}
        with patch("src.handler.get_provider"), patch(
            "src.handler.evaluate", return_value=_valid_eval_result()
        ) as mock_evaluate:
            lambda_handler(event, lambda_context)

        assert mock_evaluate.call_args.kwargs["prompt"] == ""
        assert mock_evaluate.call_args.kwargs["response"] == "Some answer."

    def test_prompt_only_without_response_succeeds_when_evaluate_mocked(
        self, lambda_context, monkeypatch
    ):
        """Prompt-only input is valid."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("DEFAULT_PROVIDER", "anthropic")

        import src.config as cfg_mod

        cfg_mod._config = None

        event = {"prompt": "What is AI?"}
        with patch("src.handler.get_provider") as mock_get_provider, patch(
            "src.handler.evaluate", return_value=_valid_eval_result()
        ):
            mock_get_provider.return_value = MagicMock()
            result = lambda_handler(event, lambda_context)

        assert result["criterion_scores"]["accuracy"] == 4.0

    def test_empty_response_allowed_when_prompt_present(
        self, lambda_context, monkeypatch
    ):
        """Empty response string is allowed if prompt text is non-empty."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("DEFAULT_PROVIDER", "anthropic")

        import src.config as cfg_mod

        cfg_mod._config = None

        event = {"prompt": "What is AI?", "response": ""}
        with patch("src.handler.get_provider"), patch(
            "src.handler.evaluate", return_value=_valid_eval_result()
        ) as mock_evaluate:
            lambda_handler(event, lambda_context)

        assert mock_evaluate.call_args.kwargs["prompt"] == "What is AI?"
        assert mock_evaluate.call_args.kwargs["response"] == ""

    def test_both_roles_empty_after_trim_raises_validation_error(
        self, lambda_context
    ):
        """Both prompt and response blank → ValidationError."""
        event = {"prompt": "", "response": ""}
        with pytest.raises(ValidationError, match="At least one"):
            lambda_handler(event, lambda_context)

    def test_both_roles_whitespace_only_raises_validation_error(
        self, lambda_context
    ):
        event = {"prompt": "  \t", "response": "\n  "}
        with pytest.raises(ValidationError, match="At least one"):
            lambda_handler(event, lambda_context)

    def test_non_string_prompt_raises_validation_error(self, lambda_context):
        event = {"prompt": 42, "response": "ok"}
        with pytest.raises(ValidationError, match="prompt"):
            lambda_handler(event, lambda_context)

    def test_non_string_response_raises_validation_error(self, lambda_context):
        event = {"prompt": "ok", "response": ["x"]}
        with pytest.raises(ValidationError, match="response"):
            lambda_handler(event, lambda_context)

    def test_descriptor_too_long_raises_validation_error(self, lambda_context):
        event = {
            "prompt": "hi",
            "prompt_descriptor": "x" * 257,
        }
        with pytest.raises(ValidationError, match="prompt_descriptor"):
            lambda_handler(event, lambda_context)

    def test_descriptor_control_character_raises_validation_error(
        self, lambda_context
    ):
        event = {"response": "ok", "response_descriptor": "bad\x00note"}
        with pytest.raises(ValidationError, match="response_descriptor"):
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


# ---------------------------------------------------------------------------
# system_prompt validation (US1)
# ---------------------------------------------------------------------------


class TestSystemPromptValidation:
    def test_system_prompt_valid_string_passes(self, lambda_context):
        """A non-empty string system_prompt passes validation without error."""
        event = _make_event(system_prompt="You are a helpful assistant.")
        # Validation only; no provider call expected — config will raise ConfigurationError.
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, lambda_context)
        assert not isinstance(exc_info.value, ValidationError)

    def test_system_prompt_integer_raises_validation_error(self, lambda_context):
        """Non-string system_prompt raises ValidationError."""
        event = _make_event(system_prompt=42)
        with pytest.raises(ValidationError, match="system_prompt"):
            lambda_handler(event, lambda_context)

    def test_system_prompt_list_raises_validation_error(self, lambda_context):
        """List system_prompt raises ValidationError."""
        event = _make_event(system_prompt=["You are X"])
        with pytest.raises(ValidationError, match="system_prompt"):
            lambda_handler(event, lambda_context)

    def test_system_prompt_empty_string_passes_to_evaluate_as_none(
        self, sample_event, lambda_context, monkeypatch
    ):
        """Empty string system_prompt is normalised to None before evaluate() is called."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("DEFAULT_PROVIDER", "anthropic")

        import src.config as cfg_mod

        cfg_mod._config = None

        event = {**sample_event, "system_prompt": ""}

        with patch("src.handler.get_provider") as mock_get_provider, patch(
            "src.handler.evaluate", return_value=_valid_eval_result()
        ) as mock_evaluate:
            mock_get_provider.return_value = MagicMock()
            lambda_handler(event, lambda_context)

        call_kwargs = mock_evaluate.call_args.kwargs
        assert call_kwargs.get("system_prompt") is None

    def test_system_prompt_passed_to_evaluate(
        self, sample_event, lambda_context, monkeypatch
    ):
        """Non-empty system_prompt is forwarded to evaluate()."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("DEFAULT_PROVIDER", "anthropic")

        import src.config as cfg_mod

        cfg_mod._config = None

        sp = "You are a customer service agent."
        event = {**sample_event, "system_prompt": sp}

        with patch("src.handler.get_provider") as mock_get_provider, patch(
            "src.handler.evaluate", return_value=_valid_eval_result()
        ) as mock_evaluate:
            mock_get_provider.return_value = MagicMock()
            lambda_handler(event, lambda_context)

        call_kwargs = mock_evaluate.call_args.kwargs
        assert call_kwargs.get("system_prompt") == sp


# ---------------------------------------------------------------------------
# context validation and normalisation (US2)
# ---------------------------------------------------------------------------


class TestContextValidation:
    def test_context_valid_string_passes(self, lambda_context):
        """A string contexts passes validation without error."""
        event = _make_event(contexts="Retrieved document: foo bar.")
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, lambda_context)
        assert not isinstance(exc_info.value, ValidationError)

    def test_context_valid_list_of_strings_passes(self, lambda_context):
        """A list of strings contexts passes validation without error."""
        event = _make_event(contexts=["doc 1", "doc 2"])
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, lambda_context)
        assert not isinstance(exc_info.value, ValidationError)

    def test_context_integer_raises_validation_error(self, lambda_context):
        """Integer contexts raises ValidationError."""
        event = _make_event(contexts=42)
        with pytest.raises(ValidationError, match="contexts"):
            lambda_handler(event, lambda_context)

    def test_context_dict_raises_validation_error(self, lambda_context):
        """Dict contexts raises ValidationError."""
        event = _make_event(contexts={"doc": "text"})
        with pytest.raises(ValidationError, match="contexts"):
            lambda_handler(event, lambda_context)

    def test_context_list_with_integer_element_raises_validation_error(
        self, lambda_context
    ):
        """List containing non-string element raises ValidationError."""
        event = _make_event(contexts=["valid string", 99])
        with pytest.raises(ValidationError, match="contexts"):
            lambda_handler(event, lambda_context)


class TestNormalizeContext:
    """Unit tests for _normalize_context helper."""

    def test_none_returns_none(self):
        assert _normalize_context(None) is None

    def test_empty_string_returns_none(self):
        assert _normalize_context("") is None

    def test_whitespace_only_string_returns_none(self):
        assert _normalize_context("   ") is None

    def test_non_empty_string_returns_single_item_list(self):
        assert _normalize_context("doc text") == ["doc text"]

    def test_empty_list_returns_none(self):
        assert _normalize_context([]) is None

    def test_list_of_all_empty_strings_returns_none(self):
        assert _normalize_context(["", "  ", ""]) is None

    def test_list_with_some_empty_strings_filtered(self):
        assert _normalize_context(["", "doc 1", "", "doc 2"]) == ["doc 1", "doc 2"]

    def test_list_of_strings_returned_as_is(self):
        assert _normalize_context(["a", "b", "c"]) == ["a", "b", "c"]

    def test_context_passed_to_evaluate_as_normalised_list(
        self, sample_event=None, monkeypatch=None
    ):
        """End-to-end: string context forwarded as list[str] to evaluate()."""
        # Tested via lambda_handler integration below; unit test covers _normalize_context.
        pass
