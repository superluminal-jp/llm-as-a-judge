"""Shared pytest fixtures for LLM-as-a-Judge test suite.

All fixtures use mocks — no real API calls are made in any test.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Event fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_event() -> dict:
    """Minimal valid Lambda event with prompt and response."""
    return {
        "prompt": "What is machine learning?",
        "response": "Machine learning is a subset of AI that enables systems to learn from data.",
    }


@pytest.fixture
def sample_event_with_provider(sample_event: dict) -> dict:
    """Lambda event that explicitly sets the Anthropic provider."""
    return {**sample_event, "provider": "anthropic"}


# ---------------------------------------------------------------------------
# Lambda context fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def lambda_context() -> MagicMock:
    """Mock AWS Lambda context object."""
    ctx = MagicMock()
    ctx.aws_request_id = "test-req-id-1234"
    ctx.function_name = "llm-judge-test"
    ctx.memory_limit_in_mb = 512
    ctx.get_remaining_time_in_millis.return_value = 55_000
    return ctx


# ---------------------------------------------------------------------------
# LLM response fixtures
# ---------------------------------------------------------------------------


def _make_criterion_scores(*names: str) -> dict:
    """Return a score of 4.0 for every supplied criterion name."""
    return {name: 4.0 for name in names}


BALANCED_CRITERIA_NAMES = ("accuracy", "clarity", "helpfulness", "completeness")


def _balanced_response_json(scores: dict | None = None) -> str:
    """Return a JSON string representing a complete evaluation response."""
    if scores is None:
        scores = _make_criterion_scores(*BALANCED_CRITERIA_NAMES)
    payload = {
        "criterion_scores": scores,
        "reasoning": "The response is factually correct, clearly written, and helpful.",
    }
    return json.dumps(payload)


@pytest.fixture
def mock_anthropic_response() -> MagicMock:
    """Mock anthropic.types.Message with a valid evaluation JSON body."""
    message = MagicMock()
    message.content = [MagicMock(text=_balanced_response_json())]
    return message


@pytest.fixture
def mock_openai_response() -> MagicMock:
    """Mock openai ChatCompletion response with a valid evaluation JSON body."""
    choice = MagicMock()
    choice.message.content = _balanced_response_json()
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.fixture
def mock_bedrock_response() -> dict:
    """Mock Bedrock converse API response dict with a valid evaluation JSON body."""
    return {
        "output": {
            "message": {
                "content": [{"text": _balanced_response_json()}]
            }
        }
    }


# ---------------------------------------------------------------------------
# Config / env-var fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=False)
def env_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Populate environment variables for Anthropic provider tests."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("DEFAULT_PROVIDER", "anthropic")


@pytest.fixture(autouse=False)
def env_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """Populate environment variables for OpenAI provider tests."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    monkeypatch.setenv("DEFAULT_PROVIDER", "openai")


@pytest.fixture(autouse=False)
def env_bedrock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Populate environment variables for Bedrock provider tests."""
    monkeypatch.setenv("BEDROCK_MODEL", "amazon.nova-premier-v1:0")
    monkeypatch.setenv("DEFAULT_PROVIDER", "bedrock")
