"""Shared Powertools tracing and metrics instruments for LLM-as-a-Judge.

Every module imports the singletons defined here rather than constructing its
own, so that traces share one segment tree and metrics land in a single EMF blob
per invocation.

Tracing
    :data:`tracer` wraps the AWS X-Ray SDK. Powertools selects X-Ray over the
    OpenTelemetry distro specifically for lower cold-start latency. The Tracer
    disables itself automatically when not running inside Lambda, so importing
    this module is safe in tests and local scripts.

Metrics
    :data:`metrics` emits CloudWatch Embedded Metric Format (EMF) to stdout.
    CloudWatch extracts the metrics asynchronously from the log stream, so there
    is no synchronous PutMetricData call on the request path and no additional
    IAM permission to grant.

    Metric names are referenced by the CloudWatch dashboard in ``cdk/stack.py``;
    keep :data:`MetricName` and that dashboard in step.
"""

from __future__ import annotations

import os
from typing import Final

from aws_lambda_powertools import Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit

SERVICE_NAME: Final = "llm-judge"

# Namespace is normally supplied by POWERTOOLS_METRICS_NAMESPACE (set by the CDK
# stack). The literal default keeps local runs and the test suite working, since
# Metrics raises at flush time when no namespace is resolvable.
METRICS_NAMESPACE: Final = os.environ.get("POWERTOOLS_METRICS_NAMESPACE", "LlmJudge")

tracer = Tracer(service=SERVICE_NAME)
metrics = Metrics(namespace=METRICS_NAMESPACE, service=SERVICE_NAME)


class MetricName:
    """Metric names emitted by this service.

    Mirrored by the "Judge outcomes (EMF)" dashboard widget in ``cdk/stack.py``.
    """

    EVALUATIONS_COMPLETED: Final = "EvaluationsCompleted"
    EVALUATIONS_FAILED: Final = "EvaluationsFailed"
    CRITERION_EVALUATION_FAILED: Final = "CriterionEvaluationFailed"
    NOT_ASSESSABLE_COUNT: Final = "NotAssessableCount"
    BEDROCK_THROTTLED: Final = "BedrockThrottled"
    JUDGE_LATENCY_MS: Final = "JudgeLatencyMs"


def add_count(name: str, value: int = 1) -> None:
    """Record a count metric, ignoring failures.

    Instrumentation must never be the reason an evaluation fails, so any error
    raised while recording (an invalid namespace, a full metric set) is
    swallowed rather than propagated to the caller.

    Args:
        name:  Metric name, normally a :class:`MetricName` constant.
        value: Amount to add. Defaults to 1.
    """
    try:
        metrics.add_metric(name=name, unit=MetricUnit.Count, value=value)
    except Exception:  # noqa: BLE001 — telemetry must not break the request
        pass


def add_latency_ms(name: str, value: float) -> None:
    """Record a millisecond duration metric, ignoring failures.

    Args:
        name:  Metric name, normally a :class:`MetricName` constant.
        value: Duration in milliseconds.
    """
    try:
        metrics.add_metric(name=name, unit=MetricUnit.Milliseconds, value=value)
    except Exception:  # noqa: BLE001 — telemetry must not break the request
        pass
