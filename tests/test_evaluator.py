"""Tests for the evaluator module (src/evaluator.py).

Covers:
- Prompt construction includes all criterion names.
- Valid JSON response is parsed into an evaluation result dict.
- Invalid/missing JSON raises ProviderError.
- Overall score is computed as a weighted average.
- evaluate() orchestrates the full pipeline correctly.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.criteria import CriterionDefinition, DefaultCriteria, EvaluationCriteria
from src.evaluator import build_evaluation_prompt, evaluate, parse_evaluation_response
from src.handler import ProviderError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def balanced_criteria() -> EvaluationCriteria:
    return DefaultCriteria.balanced()


@pytest.fixture
def simple_criteria() -> EvaluationCriteria:
    return EvaluationCriteria(
        name="Simple",
        criteria=[
            CriterionDefinition(name="accuracy", description="Is it correct?", weight=2.0),
            CriterionDefinition(name="clarity", description="Is it clear?", weight=1.0),
        ],
    )


def _make_raw_response(scores: dict, reasoning: str = "Good.") -> str:
    return json.dumps({"criterion_scores": scores, "reasoning": reasoning})


# ---------------------------------------------------------------------------
# build_evaluation_prompt
# ---------------------------------------------------------------------------


class TestBuildEvaluationPrompt:
    def test_prompt_contains_all_criterion_names(self, balanced_criteria):
        prompt = build_evaluation_prompt(
            prompt="What is AI?",
            response="AI stands for Artificial Intelligence.",
            criteria=balanced_criteria,
        )
        for criterion in balanced_criteria.criteria:
            assert criterion.name in prompt

    def test_prompt_contains_user_prompt(self, balanced_criteria):
        user_prompt = "Explain quantum computing."
        prompt = build_evaluation_prompt(
            prompt=user_prompt,
            response="It uses qubits.",
            criteria=balanced_criteria,
        )
        assert user_prompt in prompt

    def test_prompt_contains_response_text(self, balanced_criteria):
        response_text = "A unique response string 12345."
        prompt = build_evaluation_prompt(
            prompt="Q?",
            response=response_text,
            criteria=balanced_criteria,
        )
        assert response_text in prompt

    def test_prompt_requests_json_output(self, balanced_criteria):
        prompt = build_evaluation_prompt("Q", "A", balanced_criteria)
        assert "json" in prompt.lower() or "JSON" in prompt


# ---------------------------------------------------------------------------
# parse_evaluation_response
# ---------------------------------------------------------------------------


class TestParseEvaluationResponse:
    def test_parse_valid_json_response(self, balanced_criteria):
        scores = {c.name: 4.0 for c in balanced_criteria.criteria}
        raw = _make_raw_response(scores)

        result = parse_evaluation_response(
            raw_text=raw,
            criteria=balanced_criteria,
            judge_model="claude-sonnet-4-6",
            provider="anthropic",
        )

        assert result["overall_score"] == pytest.approx(4.0)
        assert result["criterion_scores"] == scores
        assert result["reasoning"] == "Good."
        assert result["judge_model"] == "claude-sonnet-4-6"
        assert result["provider"] == "anthropic"

    def test_parse_json_inside_code_block(self, balanced_criteria):
        """JSON wrapped in ```json ... ``` fences should be extracted correctly."""
        scores = {c.name: 3.0 for c in balanced_criteria.criteria}
        inner = json.dumps({"criterion_scores": scores, "reasoning": "OK."})
        raw = f"```json\n{inner}\n```"

        result = parse_evaluation_response(raw, balanced_criteria, "m", "p")

        assert result["overall_score"] == pytest.approx(3.0)

    def test_parse_invalid_json_raises_provider_error(self, balanced_criteria):
        with pytest.raises(ProviderError, match="parse"):
            parse_evaluation_response(
                raw_text="not-json",
                criteria=balanced_criteria,
                judge_model="m",
                provider="p",
            )

    def test_missing_criterion_scores_key_raises_provider_error(self, balanced_criteria):
        raw = json.dumps({"reasoning": "Missing scores."})
        with pytest.raises(ProviderError):
            parse_evaluation_response(raw, balanced_criteria, "m", "p")

    def test_missing_criterion_name_in_scores_raises_provider_error(self, balanced_criteria):
        """If the LLM returns scores for fewer criteria than expected, raise ProviderError."""
        partial_scores = {"accuracy": 4.0}  # missing clarity, helpfulness, completeness
        raw = _make_raw_response(partial_scores)
        with pytest.raises(ProviderError, match="criterion"):
            parse_evaluation_response(raw, balanced_criteria, "m", "p")


# ---------------------------------------------------------------------------
# Weighted average calculation
# ---------------------------------------------------------------------------


class TestOverallScoreCalculation:
    def test_equal_weights_overall_score_is_arithmetic_mean(self, balanced_criteria):
        scores = {"accuracy": 5.0, "clarity": 3.0, "helpfulness": 4.0, "completeness": 4.0}
        raw = _make_raw_response(scores)
        result = parse_evaluation_response(raw, balanced_criteria, "m", "p")
        expected_mean = (5.0 + 3.0 + 4.0 + 4.0) / 4
        assert result["overall_score"] == pytest.approx(expected_mean)

    def test_unequal_weights_apply_correctly(self, simple_criteria):
        """accuracy(weight=2) and clarity(weight=1) → weighted average."""
        scores = {"accuracy": 5.0, "clarity": 2.0}
        raw = _make_raw_response(scores)
        result = parse_evaluation_response(raw, simple_criteria, "m", "p")
        # (5.0*2 + 2.0*1) / (2+1) = 12/3 = 4.0
        assert result["overall_score"] == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# evaluate() orchestration
# ---------------------------------------------------------------------------


class TestEvaluate:
    def test_evaluate_calls_provider_complete(self, balanced_criteria):
        mock_provider = MagicMock()
        scores = {c.name: 4.0 for c in balanced_criteria.criteria}
        mock_provider.complete.return_value = _make_raw_response(scores)

        result = evaluate(
            prompt="Q?",
            response="A.",
            criteria=balanced_criteria,
            provider=mock_provider,
            model="claude-sonnet-4-6",
            timeout=30,
        )

        mock_provider.complete.assert_called_once()
        assert result["overall_score"] == pytest.approx(4.0)

    def test_evaluate_provider_error_propagates(self, balanced_criteria):
        mock_provider = MagicMock()
        mock_provider.complete.side_effect = ProviderError("Timeout")

        with pytest.raises(ProviderError, match="Timeout"):
            evaluate(
                prompt="Q?",
                response="A.",
                criteria=balanced_criteria,
                provider=mock_provider,
                model="m",
                timeout=30,
            )
