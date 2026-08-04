"""Tests for src/observability.py and the instrumentation it feeds.

The point of these tests is not that metrics have particular values, but that
instrumentation is wired to the paths that matter and — critically — that a
failure inside instrumentation can never take down an evaluation.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.criteria import CriterionDefinition, EvaluationCriteria
from src.errors import ProviderError
from src.observability import MetricName, add_count, add_latency_ms


def _criterion_json(score: float = 4.0, assessability: str = "assessed") -> str:
    payload: dict = {"assessability": assessability, "reasoning": "because"}
    if assessability == "assessed":
        payload["score"] = score
    return json.dumps(payload)


def _criteria(*names: str) -> EvaluationCriteria:
    return EvaluationCriteria(
        name="T",
        criteria=[CriterionDefinition(name=n, description=f"{n} desc") for n in names],
    )


# ---------------------------------------------------------------------------
# Instrumentation must never break the request
# ---------------------------------------------------------------------------


class TestTelemetryIsNonFatal:
    def test_add_count_swallows_errors(self) -> None:
        with patch(
            "src.observability.metrics.add_metric", side_effect=RuntimeError("boom")
        ):
            add_count(MetricName.EVALUATIONS_COMPLETED)  # must not raise

    def test_add_latency_swallows_errors(self) -> None:
        with patch(
            "src.observability.metrics.add_metric", side_effect=ValueError("bad unit")
        ):
            add_latency_ms(MetricName.JUDGE_LATENCY_MS, 12.5)  # must not raise

    def test_evaluation_survives_broken_metrics(self) -> None:
        """A metrics backend failure must not fail an otherwise good evaluation."""
        from src.evaluator import _evaluate_one_criterion

        provider = MagicMock()
        provider.complete.return_value = _criterion_json()

        with patch(
            "src.observability.metrics.add_metric", side_effect=RuntimeError("boom")
        ):
            name, assessability, score, _ = _evaluate_one_criterion(
                _criteria("accuracy").criteria[0],
                "Q?",
                "A.",
                has_prompt=True,
                has_response=True,
                prompt_descriptor=None,
                response_descriptor=None,
                provider=provider,
                model="m",
                timeout=30,
                provider_label="bedrock",
            )

        assert (name, assessability, score) == ("accuracy", "assessed", 4.0)


# ---------------------------------------------------------------------------
# Metrics are emitted on the paths that matter
# ---------------------------------------------------------------------------


class TestBedrockThrottleMetric:
    def test_throttling_is_counted(self) -> None:
        import botocore.exceptions

        from src.config import Config
        from src.providers.bedrock import BedrockProvider

        config = Config(
            default_provider="bedrock",
            anthropic_api_key="",
            anthropic_model="m",
            openai_api_key="",
            openai_model="m",
            bedrock_model="m",
            request_timeout=30,
            log_level="INFO",
        )

        client = MagicMock()
        client.converse.side_effect = botocore.exceptions.ClientError(
            error_response={
                "Error": {"Code": "ThrottlingException", "Message": "slow down"}
            },
            operation_name="Converse",
        )

        with patch("src.providers.bedrock.boto3.client", return_value=client):
            provider = BedrockProvider(config)
            with patch("src.providers.bedrock.add_count") as add:
                with pytest.raises(ProviderError):
                    provider.complete(
                        [{"role": "user", "content": "hi"}], "m", 30
                    )

        assert [
            c for c in add.call_args_list if c.args[0] == MetricName.BEDROCK_THROTTLED
        ], "throttling was not counted"


# ---------------------------------------------------------------------------
# Dashboard / code agreement
# ---------------------------------------------------------------------------


class TestDashboardReferencesRealMetrics:
    def test_dashboard_metric_names_exist_in_code(self) -> None:
        """The dashboard widget must not chart metrics nothing emits."""
        import os
        import re

        stack_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "cdk", "stack.py"
        )
        with open(stack_path, encoding="utf-8") as handle:
            stack_source = handle.read()

        widget = re.search(
            r'"EvaluationsCompleted",.*?\)\s*\n\s*\],', stack_source, re.DOTALL
        )
        assert widget, "EMF dashboard widget not found in cdk/stack.py"

        charted = set(re.findall(r'"([A-Z][A-Za-z]+)"', widget.group(0)))
        known = {
            value
            for name, value in vars(MetricName).items()
            if not name.startswith("_") and isinstance(value, str)
        }
        assert charted <= known, f"dashboard charts unknown metrics: {charted - known}"
