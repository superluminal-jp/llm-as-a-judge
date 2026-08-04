"""Tests for the evaluator module (src/evaluator.py).

Covers the pure building blocks the workflow steps compose:

- Single-criterion judge prompt construction, including single-sided
  submissions, operator descriptors, system prompts, and retrieval contexts.
- Single-criterion response parsing (assessability, optional score, reasoning).
- Summary prompt construction.

Orchestration is not tested here. The fan-out across criteria belongs to the
Step Functions Map state; see tests/test_cdk_stack.py for its concurrency and
retry configuration, and tests/test_workflow_handlers.py for the step handlers.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from src.criteria import CriterionDefinition, EvaluationCriteria
from src.evaluator import (
    ASSESSABILITY_ASSESSED,
    ASSESSABILITY_NOT_ASSESSABLE,
    _render_context_section,
    build_evaluation_prompt_single_criterion,
    build_summary_prompt,
    parse_single_criterion_response,
)
from src.errors import ProviderError

# Keyword-only flags for paired evaluation in unit tests.
_PAIRED_ROLES = {"has_prompt": True, "has_response": True}


def _judge_criterion_json(
    score: float | None,
    reasoning: str,
    *,
    assessability: str = ASSESSABILITY_ASSESSED,
    step_reasoning: list[str] | None = None,
) -> str:
    payload: dict = {
        "assessability": assessability,
        "reasoning": reasoning,
    }
    if assessability == ASSESSABILITY_ASSESSED and score is not None:
        payload["score"] = score
    if step_reasoning is not None:
        payload["step_reasoning"] = step_reasoning
    return json.dumps(payload)


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
            prompt="Q?", response="A.", criterion=criterion, **_PAIRED_ROLES
        )
        assert criterion.name in prompt
        assert criterion.description in prompt

    def test_prompt_requests_score_and_reasoning(self, simple_criteria):
        criterion = simple_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion(
            "Q", "A", criterion, **_PAIRED_ROLES
        )
        assert "score" in prompt.lower()
        assert "reasoning" in prompt.lower()
        assert "assessability" in prompt.lower()

    def test_prompt_with_evaluation_steps_includes_steps(self, stepped_criteria):
        criterion = stepped_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion(
            "Q", "A", criterion, **_PAIRED_ROLES
        )
        assert "Evaluation Steps" in prompt
        assert "1. Are all facts verifiable?" in prompt
        assert "2. Are there contradictions?" in prompt
        assert "step_reasoning" in prompt

    def test_prompt_without_steps_omits_step_section(self, simple_criteria):
        criterion = simple_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion(
            "Q", "A", criterion, **_PAIRED_ROLES
        )
        assert "Evaluation Steps" not in prompt
        assert "step_reasoning" not in prompt


class TestSingleSidedSubmissionSections:
    """Prompt-only / response-only: placeholders and headings (US2, US3)."""

    def test_prompt_only_shows_placeholder_for_response_role(self, simple_criteria):
        criterion = simple_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Instruction only",
            response="",
            criterion=criterion,
            has_prompt=True,
            has_response=False,
        )
        assert "## Text in prompt role" in prompt
        assert "Instruction only" in prompt
        assert "## Text in response role" in prompt
        assert "*(No text supplied for this role in this evaluation.)*" in prompt

    def test_response_only_shows_placeholder_for_prompt_role(self, simple_criteria):
        criterion = simple_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion(
            prompt="",
            response="Standalone answer text.",
            criterion=criterion,
            has_prompt=False,
            has_response=True,
        )
        assert "## Text in response role" in prompt
        assert "Standalone answer text." in prompt
        assert "## Text in prompt role" in prompt
        assert prompt.index("## Text in prompt role") < prompt.index(
            "## Text in response role"
        )


class TestDescriptorRenderingInJudgePrompt:
    """Optional operator notes (US4)."""

    def test_descriptors_appear_before_role_sections(self, simple_criteria):
        criterion = simple_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q",
            response="A",
            criterion=criterion,
            has_prompt=True,
            has_response=True,
            prompt_descriptor="End-user question",
            response_descriptor="Assistant output",
        )
        assert "**Operator note (prompt role):** End-user question" in prompt
        assert "**Operator note (response role):** Assistant output" in prompt
        desc_pos = prompt.index("**Operator note (prompt role):**")
        role_pos = prompt.index("## Text in prompt role")
        assert desc_pos < role_pos


# ---------------------------------------------------------------------------
# parse_single_criterion_response
# ---------------------------------------------------------------------------


class TestParseSingleCriterionResponse:
    def test_parse_valid_single_criterion_response(self):
        raw = _judge_criterion_json(4.0, "Accurate and clear.")
        assess, score, reasoning = parse_single_criterion_response(
            raw, "accuracy", "m", "p"
        )
        assert assess == ASSESSABILITY_ASSESSED
        assert score == 4.0
        assert reasoning == "Accurate and clear."

    def test_parse_single_criterion_json_in_code_block(self):
        inner = _judge_criterion_json(3.0, "OK")
        raw = f"```json\n{inner}\n```"
        assess, score, reasoning = parse_single_criterion_response(
            raw, "clarity", "m", "p"
        )
        assert assess == ASSESSABILITY_ASSESSED
        assert score == 3.0
        assert reasoning == "OK"

    def test_score_clamped_to_1_5(self):
        raw = _judge_criterion_json(10.0, "x")
        _, score, _ = parse_single_criterion_response(raw, "a", "m", "p")
        assert score == 5.0
        raw = _judge_criterion_json(0.0, "x")
        _, score, _ = parse_single_criterion_response(raw, "a", "m", "p")
        assert score == 1.0

    def test_missing_score_when_assessed_raises_provider_error(self):
        raw = json.dumps(
            {"assessability": ASSESSABILITY_ASSESSED, "reasoning": "No score."}
        )
        with pytest.raises(ProviderError, match="score"):
            parse_single_criterion_response(raw, "a", "m", "p")

    def test_not_assessable_omits_score(self):
        raw = json.dumps(
            {
                "assessability": ASSESSABILITY_NOT_ASSESSABLE,
                "reasoning": "Need both roles.",
            }
        )
        assess, score, reasoning = parse_single_criterion_response(
            raw, "a", "m", "p"
        )
        assert assess == ASSESSABILITY_NOT_ASSESSABLE
        assert score is None
        assert "Need both roles." in reasoning

    def test_step_reasoning_embedded_in_reasoning(self):
        raw = _judge_criterion_json(
            4.0,
            "Overall accurate.",
            step_reasoning=[
                "Yes, all facts verified.",
                "No contradictions found.",
            ],
        )
        assess, score, reasoning = parse_single_criterion_response(
            raw, "accuracy", "m", "p"
        )
        assert assess == ASSESSABILITY_ASSESSED
        assert score == 4.0
        assert "Step 1: Yes, all facts verified." in reasoning
        assert "Step 2: No contradictions found." in reasoning
        assert "Final: Overall accurate." in reasoning

    def test_no_step_reasoning_returns_plain_reasoning(self):
        raw = _judge_criterion_json(3.0, "Plain reasoning.")
        _, _, reasoning = parse_single_criterion_response(raw, "a", "m", "p")
        assert reasoning == "Plain reasoning."
        assert "Step" not in reasoning

    def test_backward_compat_score_without_assessability_implies_assessed(self):
        raw = json.dumps({"score": 4, "reasoning": "Legacy."})
        assess, score, _ = parse_single_criterion_response(raw, "a", "m", "p")
        assert assess == ASSESSABILITY_ASSESSED
        assert score == 4.0


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
            prompt="Q?", response="A.", criterion=criterion, **_PAIRED_ROLES
        )
        assert "## System Prompt" not in prompt

    def test_system_prompt_present_adds_section(self, simple_criteria):
        """Non-empty system_prompt adds a ## System Prompt section."""
        criterion = simple_criteria.criteria[0]
        sp = "You are a customer service agent."
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q?",
            response="A.",
            criterion=criterion,
            system_prompt=sp,
            **_PAIRED_ROLES,
        )
        assert "## System Prompt" in prompt
        assert sp in prompt

    def test_system_prompt_appears_before_prompt_role_text(self, simple_criteria):
        """## System Prompt section must precede ## Text in prompt role section."""
        criterion = simple_criteria.criteria[0]
        sp = "You are an expert."
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q?",
            response="A.",
            criterion=criterion,
            system_prompt=sp,
            **_PAIRED_ROLES,
        )
        sys_pos = prompt.index("## System Prompt")
        prompt_role_pos = prompt.index("## Text in prompt role")
        assert sys_pos < prompt_role_pos

    def test_none_system_prompt_omits_section(self, simple_criteria):
        """system_prompt=None behaves the same as omitting the argument."""
        criterion = simple_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q?",
            response="A.",
            criterion=criterion,
            system_prompt=None,
            **_PAIRED_ROLES,
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
            prompt="Q?", response="A.", criterion=criterion, **_PAIRED_ROLES
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
            **_PAIRED_ROLES,
        )
        assert "## Additional Context" in prompt
        assert "Return policy: 30 days." in prompt
        assert "[1]" not in prompt

    def test_multi_item_context_adds_numbered_subsections(self, simple_criteria):
        """Multi-item context list renders each item with [N] prefix."""
        criterion = simple_criteria.criteria[0]
        items = ["Doc one content.", "Doc two content.", "Doc three content."]
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q?",
            response="A.",
            criterion=criterion,
            contexts=items,
            **_PAIRED_ROLES,
        )
        assert "## Additional Context" in prompt
        assert "[1] Doc one content." in prompt
        assert "[2] Doc two content." in prompt
        assert "[3] Doc three content." in prompt

    def test_context_appears_after_response_role_before_criterion(
        self, simple_criteria
    ):
        """## Additional Context follows ## Text in response role and precedes criterion."""
        criterion = simple_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q?",
            response="A.",
            criterion=criterion,
            contexts=["Some context."],
            **_PAIRED_ROLES,
        )
        resp_pos = prompt.index("## Text in response role")
        ctx_pos = prompt.index("## Additional Context")
        crit_pos = prompt.index("## Criterion to Score")
        assert resp_pos < ctx_pos < crit_pos

    def test_none_context_omits_section(self, simple_criteria):
        """contexts=None behaves the same as omitting the argument."""
        criterion = simple_criteria.criteria[0]
        prompt = build_evaluation_prompt_single_criterion(
            prompt="Q?",
            response="A.",
            criterion=criterion,
            contexts=None,
            **_PAIRED_ROLES,
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
            **_PAIRED_ROLES,
        )
        sys_pos = prompt.index("## System Prompt")
        prompt_role_pos = prompt.index("## Text in prompt role")
        resp_pos = prompt.index("## Text in response role")
        ctx_pos = prompt.index("## Additional Context")
        crit_pos = prompt.index("## Criterion to Score")
        assert sys_pos < prompt_role_pos < resp_pos < ctx_pos < crit_pos


# ---------------------------------------------------------------------------
# system_prompt and contexts in build_summary_prompt (US3)
# ---------------------------------------------------------------------------


_SAMPLE_RESULTS = [
    ("accuracy", ASSESSABILITY_ASSESSED, 4.0, "Accurate."),
    ("clarity", ASSESSABILITY_ASSESSED, 3.0, "Fairly clear."),
]

_SUMMARY_PAIRED = {"has_prompt": True, "has_response": True}


class TestSummaryPromptOptionalFields:
    def test_no_optional_fields_omits_both_sections(self):
        """No system_prompt or contexts → neither ## System Prompt nor ## Additional Context."""
        prompt = build_summary_prompt(
            "Q?", "A.", _SAMPLE_RESULTS, **_SUMMARY_PAIRED
        )
        assert "## System Prompt" not in prompt
        assert "## Additional Context" not in prompt

    def test_system_prompt_only_adds_section(self):
        """system_prompt renders before ## Text in prompt role in the summary prompt."""
        sp = "You are a helpful assistant."
        prompt = build_summary_prompt(
            "Q?", "A.", _SAMPLE_RESULTS, system_prompt=sp, **_SUMMARY_PAIRED
        )
        assert "## System Prompt" in prompt
        assert sp in prompt
        sys_pos = prompt.index("## System Prompt")
        prompt_role_pos = prompt.index("## Text in prompt role")
        assert sys_pos < prompt_role_pos

    def test_contexts_only_multi_item_adds_numbered_section(self):
        """Multi-item contexts render after ## Text in response role in summary."""
        contexts = ["Doc A.", "Doc B."]
        prompt = build_summary_prompt(
            "Q?", "A.", _SAMPLE_RESULTS, contexts=contexts, **_SUMMARY_PAIRED
        )
        assert "## Additional Context" in prompt
        assert "[1] Doc A." in prompt
        assert "[2] Doc B." in prompt
        ctx_pos = prompt.index("## Additional Context")
        resp_pos = prompt.index("## Text in response role")
        results_pos = prompt.index("## Per-Criterion Results")
        assert resp_pos < ctx_pos < results_pos

    def test_both_fields_present_in_correct_order(self):
        """Both system_prompt and contexts sections appear before ## Per-Criterion Results."""
        sp = "Be concise."
        contexts = ["Reference material."]
        prompt = build_summary_prompt(
            "Q?",
            "A.",
            _SAMPLE_RESULTS,
            system_prompt=sp,
            contexts=contexts,
            **_SUMMARY_PAIRED,
        )
        sys_pos = prompt.index("## System Prompt")
        prompt_role_pos = prompt.index("## Text in prompt role")
        ctx_pos = prompt.index("## Additional Context")
        results_pos = prompt.index("## Per-Criterion Results")
        assert sys_pos < prompt_role_pos
        assert ctx_pos < results_pos


