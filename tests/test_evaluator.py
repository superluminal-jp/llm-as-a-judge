"""Tests for the evaluator module (src/evaluator.py).

Covers:
- Single-criterion prompt construction.
- Single-criterion response parsing (score + reasoning).
- evaluate() runs one LLM call per criterion in parallel and returns
  criterion_scores and 総評 reasoning (no overall_score).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from src.criteria import CriterionDefinition, EvaluationCriteria
from src.evaluator import (
    build_evaluation_prompt_single_criterion,
    evaluate,
    parse_single_criterion_response,
)
from src.handler import ProviderError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_criteria() -> EvaluationCriteria:
    return EvaluationCriteria(
        name="Simple",
        criteria=[
            CriterionDefinition(name="accuracy", description="Is it correct?"),
            CriterionDefinition(name="clarity", description="Is it clear?"),
        ],
    )


@pytest.fixture
def stepped_criteria() -> EvaluationCriteria:
    return EvaluationCriteria(
        name="Stepped",
        criteria=[
            CriterionDefinition(
                name="accuracy",
                description="Is it correct?",
                evaluation_steps=[
                    "Are all facts verifiable?",
                    "Are there contradictions?",
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# build_evaluation_prompt_single_criterion
# ---------------------------------------------------------------------------


class TestBuildEvaluationPromptSingleCriterion:
    def test_prompt_contains_criterion_name_and_description(self, simple_criteria):
        criterion = simple_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q?", response="A.", criterion=criterion
        )
        assert criterion.name in prompt
        assert criterion.description in prompt

    def test_prompt_requests_score_and_reasoning(self, simple_criteria):
        criterion = simple_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion("Q", "A", criterion)
        assert "score" in prompt.lower()
        assert "reasoning" in prompt.lower()

    def test_prompt_with_evaluation_steps_includes_steps(self, stepped_criteria):
        criterion = stepped_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion("Q", "A", criterion)
        assert "Evaluation Steps" in prompt
        assert "1. Are all facts verifiable?" in prompt
        assert "2. Are there contradictions?" in prompt
        assert "step_reasoning" in prompt

    def test_prompt_without_steps_omits_step_section(self, simple_criteria):
        criterion = simple_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion("Q", "A", criterion)
        assert "Evaluation Steps" not in prompt
        assert "step_reasoning" not in prompt


# ---------------------------------------------------------------------------
# parse_single_criterion_response
# ---------------------------------------------------------------------------


class TestParseSingleCriterionResponse:
    def test_parse_valid_single_criterion_response(self):
        raw = json.dumps({"score": 4.0, "reasoning": "Accurate and clear."})
        score, reasoning = parse_single_criterion_response(
            raw, "accuracy", "m", "p"
        )
        assert score == 4.0
        assert reasoning == "Accurate and clear."

    def test_parse_single_criterion_json_in_code_block(self):
        inner = json.dumps({"score": 3, "reasoning": "OK"})
        raw = f"```json\n{inner}\n```"
        score, reasoning = parse_single_criterion_response(
            raw, "clarity", "m", "p"
        )
        assert score == 3.0
        assert reasoning == "OK"

    def test_score_clamped_to_1_5(self):
        raw = json.dumps({"score": 10, "reasoning": "x"})
        score, _ = parse_single_criterion_response(raw, "a", "m", "p")
        assert score == 5.0
        raw = json.dumps({"score": 0, "reasoning": "x"})
        score, _ = parse_single_criterion_response(raw, "a", "m", "p")
        assert score == 1.0

    def test_missing_score_raises_provider_error(self):
        raw = json.dumps({"reasoning": "No score."})
        with pytest.raises(ProviderError, match="score"):
            parse_single_criterion_response(raw, "a", "m", "p")

    def test_step_reasoning_embedded_in_reasoning(self):
        raw = json.dumps({
            "step_reasoning": ["Yes, all facts verified.", "No contradictions found."],
            "score": 4,
            "reasoning": "Overall accurate.",
        })
        score, reasoning = parse_single_criterion_response(raw, "accuracy", "m", "p")
        assert score == 4.0
        assert "Step 1: Yes, all facts verified." in reasoning
        assert "Step 2: No contradictions found." in reasoning
        assert "Final: Overall accurate." in reasoning

    def test_no_step_reasoning_returns_plain_reasoning(self):
        raw = json.dumps({"score": 3, "reasoning": "Plain reasoning."})
        _, reasoning = parse_single_criterion_response(raw, "a", "m", "p")
        assert reasoning == "Plain reasoning."
        assert "Step" not in reasoning


# ---------------------------------------------------------------------------
# evaluate()
# ---------------------------------------------------------------------------


class TestEvaluate:
    def test_evaluate_calls_provider_per_criterion(self, simple_criteria):
        mock_provider = MagicMock()
        mock_provider.complete.side_effect = [
            json.dumps({"score": 4.0, "reasoning": "Good accuracy."}),
            json.dumps({"score": 3.0, "reasoning": "Clear enough."}),
            "accuracyは4.0と高く正確だが、clarityは3.0とやや改善の余地がある。",
        ]

        result = evaluate(
            prompt="Q?",
            response="A.",
            criteria=simple_criteria,
            provider=mock_provider,
            model="m",
            timeout=30,
        )

        # 2 criterion calls + 1 summary call
        assert mock_provider.complete.call_count == 3
        assert result["criterion_scores"] == {"accuracy": 4.0, "clarity": 3.0}
        assert "overall_score" not in result
        assert result["reasoning"] == "accuracyは4.0と高く正確だが、clarityは3.0とやや改善の余地がある。"
        assert result["criterion_reasoning"]["accuracy"] == "Good accuracy."
        assert result["criterion_reasoning"]["clarity"] == "Clear enough."

    def test_evaluate_with_steps_surfaces_step_reasoning(self, stepped_criteria):
        mock_provider = MagicMock()
        mock_provider.complete.side_effect = [
            json.dumps({
                "step_reasoning": ["Yes, facts verified.", "No contradictions."],
                "score": 4.0,
                "reasoning": "Overall accurate.",
            }),
            "accuracyは4.0。段階的な評価により事実確認と矛盾チェックを通過した。",
        ]

        result = evaluate(
            prompt="Q?",
            response="A.",
            criteria=stepped_criteria,
            provider=mock_provider,
            model="m",
            timeout=30,
        )

        assert result["criterion_scores"] == {"accuracy": 4.0}
        assert "Step 1:" in result["criterion_reasoning"]["accuracy"]
        assert "Step 2:" in result["criterion_reasoning"]["accuracy"]
        assert "Final:" in result["criterion_reasoning"]["accuracy"]

    def test_evaluate_provider_error_propagates(self, simple_criteria):
        mock_provider = MagicMock()
        mock_provider.complete.side_effect = [
            json.dumps({"score": 4.0, "reasoning": "OK."}),
            ProviderError("Rate limited"),
            "summary not reached",
        ]

        with pytest.raises(ProviderError, match="Rate limited"):
            evaluate(
                prompt="Q?",
                response="A.",
                criteria=simple_criteria,
                provider=mock_provider,
                model="m",
                timeout=30,
            )
