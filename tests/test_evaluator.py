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
    _build_summary_prompt,
    _render_context_section,
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


# ---------------------------------------------------------------------------
# _render_context_section
# ---------------------------------------------------------------------------


class TestRenderContextSection:
    def test_single_item_no_numbering(self):
        """Single-item list renders as plain text without a number prefix."""
        result = _render_context_section(["Document content here."])
        assert result == "Document content here."
        assert "[1]" not in result

    def test_two_items_numbered(self):
        """Two-item list renders with [1] and [2] prefixes."""
        result = _render_context_section(["First doc.", "Second doc."])
        assert "[1] First doc." in result
        assert "[2] Second doc." in result

    def test_three_items_numbered(self):
        """Three-item list renders with [1], [2], [3] prefixes."""
        result = _render_context_section(["a", "b", "c"])
        assert "[1] a" in result
        assert "[2] b" in result
        assert "[3] c" in result

    def test_items_separated_by_blank_line(self):
        """Multiple items are separated by a blank line."""
        result = _render_context_section(["first", "second"])
        assert "\n\n" in result


# ---------------------------------------------------------------------------
# system_prompt in build_evaluation_prompt_single_criterion (US1)
# ---------------------------------------------------------------------------


class TestSystemPromptInJudgePrompt:
    def test_no_system_prompt_omits_section(self, simple_criteria):
        """When system_prompt is absent, ## System Prompt section is not present."""
        criterion = simple_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q?", response="A.", criterion=criterion
        )
        assert "## System Prompt" not in prompt

    def test_system_prompt_present_adds_section(self, simple_criteria):
        """Non-empty system_prompt adds a ## System Prompt section."""
        criterion = simple_criteria.criteria[0]
        sp = "You are a customer service agent."
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q?", response="A.", criterion=criterion, system_prompt=sp
        )
        assert "## System Prompt" in prompt
        assert sp in prompt

    def test_system_prompt_appears_before_original_prompt(self, simple_criteria):
        """## System Prompt section must precede ## Original Prompt section."""
        criterion = simple_criteria.criteria[0]
        sp = "You are an expert."
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q?", response="A.", criterion=criterion, system_prompt=sp
        )
        sys_pos = prompt.index("## System Prompt")
        orig_pos = prompt.index("## Original Prompt")
        assert sys_pos < orig_pos

    def test_none_system_prompt_omits_section(self, simple_criteria):
        """system_prompt=None behaves the same as omitting the argument."""
        criterion = simple_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q?", response="A.", criterion=criterion, system_prompt=None
        )
        assert "## System Prompt" not in prompt


# ---------------------------------------------------------------------------
# context in build_evaluation_prompt_single_criterion (US2)
# ---------------------------------------------------------------------------


class TestContextInJudgePrompt:
    def test_no_context_omits_section(self, simple_criteria):
        """When context is absent, ## Additional Context section is not present."""
        criterion = simple_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q?", response="A.", criterion=criterion
        )
        assert "## Additional Context" not in prompt

    def test_single_item_context_adds_section_no_numbering(self, simple_criteria):
        """Single-item context list adds section with plain text (no [1] prefix)."""
        criterion = simple_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q?",
            response="A.",
            criterion=criterion,
            contexts=["Return policy: 30 days."],
        )
        assert "## Additional Context" in prompt
        assert "Return policy: 30 days." in prompt
        assert "[1]" not in prompt

    def test_multi_item_context_adds_numbered_subsections(self, simple_criteria):
        """Multi-item context list renders each item with [N] prefix."""
        criterion = simple_criteria.criteria[0]
        items = ["Doc one content.", "Doc two content.", "Doc three content."]
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q?", response="A.", criterion=criterion, contexts=items
        )
        assert "## Additional Context" in prompt
        assert "[1] Doc one content." in prompt
        assert "[2] Doc two content." in prompt
        assert "[3] Doc three content." in prompt

    def test_context_appears_after_response_before_criterion(self, simple_criteria):
        """## Additional Context appears after ## Response to Evaluate and before criterion block."""
        criterion = simple_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q?",
            response="A.",
            criterion=criterion,
            contexts=["Some context."],
        )
        resp_pos = prompt.index("## Response to Evaluate")
        ctx_pos = prompt.index("## Additional Context")
        crit_pos = prompt.index("## Criterion to Score")
        assert resp_pos < ctx_pos < crit_pos

    def test_none_context_omits_section(self, simple_criteria):
        """contexts=None behaves the same as omitting the argument."""
        criterion = simple_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q?", response="A.", criterion=criterion, contexts=None
        )
        assert "## Additional Context" not in prompt

    def test_both_system_prompt_and_context_present(self, simple_criteria):
        """Both system_prompt and contexts sections appear in correct order."""
        criterion = simple_criteria.criteria[0]
        sp = "You are an expert evaluator."
        ctx = ["Reference doc content."]
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q?",
            response="A.",
            criterion=criterion,
            system_prompt=sp,
            contexts=ctx,
        )
        sys_pos = prompt.index("## System Prompt")
        orig_pos = prompt.index("## Original Prompt")
        resp_pos = prompt.index("## Response to Evaluate")
        ctx_pos = prompt.index("## Additional Context")
        crit_pos = prompt.index("## Criterion to Score")
        assert sys_pos < orig_pos < resp_pos < ctx_pos < crit_pos


# ---------------------------------------------------------------------------
# system_prompt and contexts in _build_summary_prompt (US3)
# ---------------------------------------------------------------------------


_SAMPLE_RESULTS = [("accuracy", 4.0, "Accurate."), ("clarity", 3.0, "Fairly clear.")]


class TestSummaryPromptOptionalFields:
    def test_no_optional_fields_omits_both_sections(self):
        """No system_prompt or contexts → neither ## System Prompt nor ## Additional Context."""
        prompt = _build_summary_prompt("Q?", "A.", _SAMPLE_RESULTS)
        assert "## System Prompt" not in prompt
        assert "## Additional Context" not in prompt

    def test_system_prompt_only_adds_section(self):
        """system_prompt renders before ## Original Prompt in the summary prompt."""
        sp = "You are a helpful assistant."
        prompt = _build_summary_prompt("Q?", "A.", _SAMPLE_RESULTS, system_prompt=sp)
        assert "## System Prompt" in prompt
        assert sp in prompt
        sys_pos = prompt.index("## System Prompt")
        orig_pos = prompt.index("## Original Prompt")
        assert sys_pos < orig_pos

    def test_contexts_only_multi_item_adds_numbered_section(self):
        """Multi-item contexts renders after ## Response Evaluated in summary."""
        contexts = ["Doc A.", "Doc B."]
        prompt = _build_summary_prompt("Q?", "A.", _SAMPLE_RESULTS, contexts=contexts)
        assert "## Additional Context" in prompt
        assert "[1] Doc A." in prompt
        assert "[2] Doc B." in prompt
        ctx_pos = prompt.index("## Additional Context")
        resp_pos = prompt.index("## Response Evaluated")
        results_pos = prompt.index("## Per-Criterion Results")
        assert resp_pos < ctx_pos < results_pos

    def test_both_fields_present_in_correct_order(self):
        """Both system_prompt and contexts sections appear before ## Per-Criterion Results."""
        sp = "Be concise."
        contexts = ["Reference material."]
        prompt = _build_summary_prompt(
            "Q?", "A.", _SAMPLE_RESULTS, system_prompt=sp, contexts=contexts
        )
        sys_pos = prompt.index("## System Prompt")
        orig_pos = prompt.index("## Original Prompt")
        ctx_pos = prompt.index("## Additional Context")
        results_pos = prompt.index("## Per-Criterion Results")
        assert sys_pos < orig_pos
        assert ctx_pos < results_pos


# ---------------------------------------------------------------------------
# End-to-end mock test: evaluate() propagates both fields to all LLM calls
# ---------------------------------------------------------------------------


class TestEvaluateWithOptionalFields:
    def test_evaluate_passes_system_prompt_and_contexts_to_prompt_builder(
        self, simple_criteria
    ):
        """evaluate() forwards system_prompt and contexts to build_evaluation_prompt_single_criterion
        and to _build_summary_prompt."""
        mock_provider = MagicMock()
        mock_provider.complete.side_effect = [
            json.dumps({"score": 4.0, "reasoning": "Good accuracy."}),
            json.dumps({"score": 3.0, "reasoning": "Clear enough."}),
            "システムプロンプトを踏まえた総評。",
        ]

        sp = "You are a strict evaluator."
        contexts = ["Context doc 1.", "Context doc 2."]

        result = evaluate(
            prompt="Q?",
            response="A.",
            criteria=simple_criteria,
            provider=mock_provider,
            model="m",
            timeout=30,
            system_prompt=sp,
            contexts=contexts,
        )

        # Verify the system_prompt and both context items appeared in at least one LLM call.
        all_calls = [call.kwargs["messages"][0]["content"]
                     for call in mock_provider.complete.call_args_list]
        per_criterion_calls = all_calls[:2]
        summary_call = all_calls[2]

        for call_content in per_criterion_calls:
            assert "## System Prompt" in call_content
            assert sp in call_content
            assert "## Additional Context" in call_content
            assert "[1] Context doc 1." in call_content
            assert "[2] Context doc 2." in call_content

        assert "## System Prompt" in summary_call
        assert "## Additional Context" in summary_call

        assert result["criterion_scores"] == {"accuracy": 4.0, "clarity": 3.0}
        assert result["reasoning"] == "システムプロンプトを踏まえた総評。"
