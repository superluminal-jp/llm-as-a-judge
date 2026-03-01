"""Tests for evaluation criteria data structures and loaders (src/criteria.py).

Covers:
- load_from_dict: valid input, missing 'criteria' key, invalid criterion data.
- load_from_s3: successful load via moto, NoSuchKey error, invalid JSON.
- _parse_s3_uri: valid URI, invalid URI patterns.
- EvaluationCriteria weight normalisation.
- DefaultCriteria.balanced() sanity checks.
"""

from __future__ import annotations

import json

import boto3
import pytest
from moto import mock_aws

from src.criteria import (
    CriterionDefinition,
    DefaultCriteria,
    EvaluationCriteria,
    _parse_s3_uri,
    load_from_dict,
    load_from_s3,
)
from src.handler import ConfigurationError, CriteriaLoadError, ValidationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


VALID_CRITERIA_DICT = {
    "name": "Technical Evaluation",
    "criteria": [
        {
            "name": "accuracy",
            "description": "Factual correctness of the response.",
            "weight": 0.5,
        },
        {
            "name": "clarity",
            "description": "Clarity and readability.",
            "weight": 0.5,
        },
    ],
}

BUCKET = "test-criteria-bucket"
KEY = "criteria/technical.json"
S3_URI = f"s3://{BUCKET}/{KEY}"


@pytest.fixture
def s3_bucket():
    """Create a mocked S3 bucket with a valid criteria file."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        client.put_object(
            Bucket=BUCKET,
            Key=KEY,
            Body=json.dumps(VALID_CRITERIA_DICT).encode("utf-8"),
        )
        # Patch the module-level S3 client to point at moto's mock.
        import src.criteria as criteria_mod

        original_client = criteria_mod._s3_client
        criteria_mod._s3_client = client
        yield client
        criteria_mod._s3_client = original_client


# ---------------------------------------------------------------------------
# load_from_dict
# ---------------------------------------------------------------------------


class TestLoadFromDict:
    def test_load_from_dict_valid(self):
        """Valid dict produces correct EvaluationCriteria."""
        ec = load_from_dict(VALID_CRITERIA_DICT)
        assert ec.name == "Technical Evaluation"
        assert len(ec.criteria) == 2
        assert ec.criteria[0].name == "accuracy"
        assert ec.criteria[1].name == "clarity"

    def test_load_from_dict_missing_criteria_key(self):
        """Dict without 'criteria' key raises ValidationError."""
        with pytest.raises(ValidationError, match="criteria"):
            load_from_dict({"name": "Bad"})

    def test_load_from_dict_empty_criteria_list(self):
        """Empty 'criteria' array raises ValidationError."""
        with pytest.raises(ValidationError, match="non-empty"):
            load_from_dict({"criteria": []})

    def test_load_from_dict_missing_name_field(self):
        """Criterion without 'name' raises ValidationError."""
        with pytest.raises(ValidationError):
            load_from_dict({"criteria": [{"description": "No name."}]})

    def test_load_from_dict_default_weight_applied(self):
        """Criterion without 'weight' defaults to 1.0."""
        data = {
            "criteria": [{"name": "accuracy", "description": "Correct?"}]
        }
        ec = load_from_dict(data)
        assert ec.criteria[0].weight == 1.0

    def test_load_from_dict_uses_evaluation_prompt_and_examples(self):
        """Optional fields are populated when provided."""
        data = {
            "criteria": [
                {
                    "name": "accuracy",
                    "description": "Correct?",
                    "evaluation_prompt": "Check facts.",
                    "examples": {"1": "Wrong", "5": "Correct"},
                }
            ]
        }
        ec = load_from_dict(data)
        assert ec.criteria[0].evaluation_prompt == "Check facts."
        assert ec.criteria[0].examples == {"1": "Wrong", "5": "Correct"}


# ---------------------------------------------------------------------------
# load_from_s3
# ---------------------------------------------------------------------------


class TestLoadFromS3:
    def test_load_from_s3_success(self, s3_bucket):
        """Valid S3 object produces correct EvaluationCriteria."""
        ec = load_from_s3(S3_URI)
        assert ec.name == "Technical Evaluation"
        assert len(ec.criteria) == 2

    def test_load_from_s3_key_not_found(self, s3_bucket):
        """NoSuchKey error raises CriteriaLoadError."""
        with pytest.raises(CriteriaLoadError, match="not found"):
            load_from_s3(f"s3://{BUCKET}/nonexistent.json")

    def test_load_from_s3_invalid_json(self, s3_bucket):
        """Non-JSON S3 object raises CriteriaLoadError."""
        s3_bucket.put_object(
            Bucket=BUCKET, Key="bad.json", Body=b"not-json-content"
        )
        import src.criteria as criteria_mod

        original = criteria_mod._s3_client
        criteria_mod._s3_client = s3_bucket
        try:
            with pytest.raises(CriteriaLoadError, match="valid JSON"):
                load_from_s3(f"s3://{BUCKET}/bad.json")
        finally:
            criteria_mod._s3_client = original


# ---------------------------------------------------------------------------
# _parse_s3_uri
# ---------------------------------------------------------------------------


class TestParseS3Uri:
    def test_parse_s3_uri_valid(self):
        bucket, key = _parse_s3_uri("s3://my-bucket/path/to/file.json")
        assert bucket == "my-bucket"
        assert key == "path/to/file.json"

    def test_parse_s3_uri_no_key(self):
        """URI without a key path raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid S3 URI"):
            _parse_s3_uri("s3://bucket-only")

    def test_parse_s3_uri_http_scheme(self):
        """Non-S3 URI raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid S3 URI"):
            _parse_s3_uri("http://bucket/key.json")

    def test_parse_s3_uri_empty_string(self):
        with pytest.raises(ValidationError, match="Invalid S3 URI"):
            _parse_s3_uri("")


# ---------------------------------------------------------------------------
# EvaluationCriteria weight normalisation
# ---------------------------------------------------------------------------


class TestEvaluationCriteriaWeights:
    def test_normalised_weights_sum_to_one(self):
        ec = EvaluationCriteria(
            criteria=[
                CriterionDefinition(name="a", description="A", weight=3.0),
                CriterionDefinition(name="b", description="B", weight=1.0),
            ]
        )
        weights = ec.normalised_weights
        assert sum(weights.values()) == pytest.approx(1.0)
        assert weights["a"] == pytest.approx(0.75)
        assert weights["b"] == pytest.approx(0.25)

    def test_equal_weights_each_is_one_over_n(self):
        ec = EvaluationCriteria(
            criteria=[
                CriterionDefinition(name="x", description="X"),
                CriterionDefinition(name="y", description="Y"),
                CriterionDefinition(name="z", description="Z"),
            ]
        )
        weights = ec.normalised_weights
        for w in weights.values():
            assert w == pytest.approx(1 / 3)


# ---------------------------------------------------------------------------
# DefaultCriteria
# ---------------------------------------------------------------------------


class TestDefaultCriteria:
    def test_balanced_has_four_criteria(self):
        ec = DefaultCriteria.balanced()
        assert len(ec.criteria) == 4

    def test_balanced_criterion_names(self):
        ec = DefaultCriteria.balanced()
        names = {c.name for c in ec.criteria}
        assert names == {"accuracy", "clarity", "helpfulness", "completeness"}

    def test_balanced_weights_normalise_to_one(self):
        ec = DefaultCriteria.balanced()
        assert sum(ec.normalised_weights.values()) == pytest.approx(1.0)
