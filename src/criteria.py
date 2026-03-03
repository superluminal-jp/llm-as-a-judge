"""Evaluation criteria data structures and loaders for LLM-as-a-Judge.

Provides immutable dataclasses for defining multi-criteria evaluation rubrics,
a factory for the default balanced criteria set, and utilities for loading
criteria from S3 or plain dicts.

S3 loading uses a module-level boto3 client cached per Lambda container to
avoid re-establishing the connection on every invocation.

S3 URI format: ``s3://<bucket>/<key>``
Criteria file format: see ``contracts/criteria-file.json``
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import boto3
import botocore.exceptions
from aws_lambda_powertools import Logger

logger = Logger(service="llm-judge")

# ---------------------------------------------------------------------------
# Cold-start cache
# ---------------------------------------------------------------------------

# Cold-start: S3 client initialized once per Lambda container. The client
# reuses the underlying HTTP connection pool across invocations.
_s3_client = boto3.client("s3")

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CriterionDefinition:
    """Defines a single evaluation dimension.

    Attributes:
        name:              Unique identifier (alphanumeric + underscore).
        description:       Human-readable explanation of what is measured.
        evaluation_prompt: Optional additional guidance for the judge LLM.
        score_descriptors: Optional mapping of score value → descriptor text.
        evaluation_steps:  Optional ordered list of yes/no questions or checks
                           the judge LLM must work through before scoring.
                           When present, the LLM returns per-step reasoning
                           alongside the final score.
    """

    name: str
    description: str
    evaluation_prompt: str = ""
    score_descriptors: dict[str, str] = field(default_factory=dict)
    evaluation_steps: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate fields after dataclass initialisation.

        Raises:
            ValueError: If ``name`` is empty or contains invalid characters,
                or ``description`` is empty.
        """
        if not self.name or not re.match(r"^[a-zA-Z0-9_]+$", self.name):
            raise ValueError(
                f"Criterion name '{self.name}' must be non-empty and contain "
                "only alphanumeric characters and underscores."
            )
        if not self.description:
            raise ValueError("Criterion description must not be empty.")


@dataclass(frozen=True)
class EvaluationCriteria:
    """A collection of evaluation criteria.

    Attributes:
        criteria: Ordered list of :class:`CriterionDefinition` items.
        name:     Human-readable label for this criteria set.
    """

    criteria: list[CriterionDefinition]
    name: str = "Evaluation Criteria"

    def __post_init__(self) -> None:
        """Validate criteria list.

        Raises:
            ValueError: If ``criteria`` is empty.
        """
        if not self.criteria:
            raise ValueError("EvaluationCriteria must contain at least one criterion.")


# ---------------------------------------------------------------------------
# Default criteria
# ---------------------------------------------------------------------------


class DefaultCriteria:
    """Factory for built-in evaluation criteria sets."""

    @staticmethod
    def balanced() -> EvaluationCriteria:
        """Return a general-purpose balanced criteria set.

        Includes four dimensions suitable for most evaluation tasks when
        no custom criteria file is specified.

        Returns:
            :class:`EvaluationCriteria` with accuracy, clarity, helpfulness,
            and completeness criteria.
        """
        return EvaluationCriteria(
            name="Balanced Evaluation",
            criteria=[
                CriterionDefinition(
                    name="accuracy",
                    description="Factual correctness of the response.",
                    evaluation_prompt=(
                        "Verify whether all claims are factually correct. "
                        "Penalise hallucinations or contradictions."
                    ),
                ),
                CriterionDefinition(
                    name="clarity",
                    description="Clarity and readability of the explanation.",
                    evaluation_prompt=(
                        "Assess whether the response is easy to follow, "
                        "well-structured, and free of ambiguous language."
                    ),
                ),
                CriterionDefinition(
                    name="helpfulness",
                    description="Practical usefulness of the response to the user.",
                    evaluation_prompt=(
                        "Consider whether the response directly addresses the "
                        "user's need and provides actionable information."
                    ),
                ),
                CriterionDefinition(
                    name="completeness",
                    description="Coverage of all relevant aspects of the question.",
                    evaluation_prompt=(
                        "Check whether important aspects of the question are "
                        "addressed without unnecessary omission."
                    ),
                ),
            ],
        )


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_from_dict(data: dict[str, Any]) -> EvaluationCriteria:
    """Construct :class:`EvaluationCriteria` from a parsed JSON dict.

    Args:
        data: Dict matching the ``contracts/criteria-file.json`` schema.

    Returns:
        Populated :class:`EvaluationCriteria`.

    Raises:
        ValidationError: If ``data`` is missing the required ``criteria`` key
            or contains invalid criterion definitions.
    """
    # Import here to avoid circular dependency (handler imports criteria).
    from src.handler import ValidationError

    if "criteria" not in data:
        logger.warning(
            "Criteria dict validation failed: missing 'criteria' key",
            extra={"keys_present": list(data.keys())},
        )
        raise ValidationError(
            "Criteria file is missing the required 'criteria' key."
        )

    raw_criteria = data["criteria"]
    if not isinstance(raw_criteria, list) or len(raw_criteria) == 0:
        logger.warning(
            "Criteria dict validation failed: 'criteria' not a non-empty array",
            extra={
                "type": type(raw_criteria).__name__,
                "length": len(raw_criteria) if isinstance(raw_criteria, list) else None,
            },
        )
        raise ValidationError(
            "'criteria' must be a non-empty array."
        )

    try:
        criterion_list = [
            CriterionDefinition(
                name=c["name"],
                description=c["description"],
                evaluation_prompt=c.get("evaluation_prompt", ""),
                score_descriptors=c.get("score_descriptors", {}),
                evaluation_steps=c.get("evaluation_steps", []),
            )
            for c in raw_criteria
        ]
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning(
            "Criteria dict validation failed: invalid criterion definition",
            extra={"error_type": type(exc).__name__, "error": str(exc)},
        )
        raise ValidationError(
            f"Invalid criterion definition: {exc}"
        ) from exc

    return EvaluationCriteria(
        name=data.get("name", "Custom Criteria"),
        criteria=criterion_list,
    )


def _parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """Parse an S3 URI into bucket and key components.

    Args:
        s3_uri: URI of the form ``s3://<bucket>/<key>``.

    Returns:
        Tuple of ``(bucket, key)``.

    Raises:
        ValidationError: If the URI does not match the expected format.
    """
    from src.handler import ValidationError

    match = re.match(r"^s3://([^/]+)/(.+)$", s3_uri)
    if not match:
        raise ValidationError(
            f"Invalid S3 URI '{s3_uri}'. Expected format: s3://<bucket>/<key>"
        )
    return match.group(1), match.group(2)


def load_from_s3(s3_uri: str) -> EvaluationCriteria:
    """Download and parse a criteria JSON file from S3.

    Args:
        s3_uri: S3 URI pointing to a JSON file matching
                ``contracts/criteria-file.json``.

    Returns:
        Populated :class:`EvaluationCriteria`.

    Raises:
        ValidationError: If the URI is malformed.
        CriteriaLoadError: If the object is not found or contains invalid JSON.
        ConfigurationError: If the Lambda execution role lacks ``s3:GetObject``
            permission on the target bucket.
    """
    from src.handler import ConfigurationError, CriteriaLoadError

    bucket, key = _parse_s3_uri(s3_uri)

    try:
        response = _s3_client.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read().decode("utf-8")
    except botocore.exceptions.ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code == "NoSuchKey":
            logger.error(
                "Criteria file not found in S3",
                extra={"s3_uri": s3_uri},
                exc_info=True,
            )
            raise CriteriaLoadError(
                f"Criteria file not found: {s3_uri}"
            ) from exc
        if error_code in ("AccessDenied", "403"):
            logger.error(
                "Access denied to S3 criteria file",
                extra={"s3_uri": s3_uri},
                exc_info=True,
            )
            raise ConfigurationError(
                f"Lambda execution role lacks s3:GetObject on {s3_uri}"
            ) from exc
        logger.error(
            "Unexpected S3 error loading criteria",
            extra={"s3_uri": s3_uri, "error_code": error_code},
            exc_info=True,
        )
        raise CriteriaLoadError(
            f"Failed to load criteria from {s3_uri}: {error_code}"
        ) from exc

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        logger.error(
            "Criteria file contains invalid JSON",
            extra={"s3_uri": s3_uri},
            exc_info=True,
        )
        raise CriteriaLoadError(
            f"Criteria file at {s3_uri} is not valid JSON: {exc}"
        ) from exc

    criteria = load_from_dict(data)
    logger.info(
        "Criteria loaded from S3",
        extra={"s3_uri": s3_uri, "criteria_count": len(criteria.criteria)},
    )
    return criteria
