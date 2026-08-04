"""Tests for the Step Functions step handlers and the claim-check job store.

The most important assertion here is
:meth:`TestWorkflowMatchesDirectInvoke.test_identical_response`: the workflow and
the single-Lambda path must produce byte-identical responses, because both are
public entry points and ``contracts/lambda-response.json`` describes both.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from src.handler import ConfigurationError, ValidationError

JOBS_BUCKET = "llm-judge-jobs-test"


def _criterion_json(score: float = 4.0, reasoning: str = "because") -> str:
    return json.dumps(
        {"assessability": "assessed", "score": score, "reasoning": reasoning}
    )


@pytest.fixture
def jobs_bucket(monkeypatch: pytest.MonkeyPatch):
    """An in-memory S3 bucket standing in for the claim-check jobs bucket."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=JOBS_BUCKET)
        monkeypatch.setenv("JOBS_BUCKET", JOBS_BUCKET)

        import src.jobs

        monkeypatch.setattr(src.jobs, "_s3_client", client)
        # The container-level cache would otherwise leak payloads between tests.
        monkeypatch.setattr(src.jobs, "_job_cache", {})
        yield client


@pytest.fixture
def bedrock_env(monkeypatch: pytest.MonkeyPatch):
    """Bedrock-only configuration with the cold-start config cache cleared."""
    monkeypatch.setenv("DEFAULT_PROVIDER", "bedrock")
    monkeypatch.setenv("BEDROCK_MODEL", "amazon.nova-lite-v1:0")
    monkeypatch.delenv("API_KEYS_SECRET_NAME", raising=False)

    import src.config

    monkeypatch.setattr(src.config, "_config", None)
    yield
    monkeypatch.setattr(src.config, "_config", None)


@pytest.fixture
def lambda_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.aws_request_id = "req-1"
    return ctx


SAMPLE_EVENT = {
    "prompt": "機械学習とは？",
    "response": "AIの一分野です。",
}


# ---------------------------------------------------------------------------
# src/jobs.py
# ---------------------------------------------------------------------------


class TestJobStore:
    def test_round_trip(self, jobs_bucket) -> None:
        from src.jobs import get_job, put_job

        uri = put_job(JOBS_BUCKET, {"hello": "世界"})
        assert uri.startswith(f"s3://{JOBS_BUCKET}/jobs/")
        assert get_job(uri) == {"hello": "世界"}

    def test_non_ascii_survives_the_round_trip(self, jobs_bucket) -> None:
        """Submissions are frequently Japanese; encoding must be lossless."""
        from src.jobs import get_job, put_job

        payload = {"prompt": "評価対象の日本語テキスト", "contexts": ["参考資料[1]"]}
        assert get_job(put_job(JOBS_BUCKET, payload)) == payload

    def test_second_read_is_served_from_cache(self, jobs_bucket) -> None:
        """Map branches share a container; re-reading S3 per branch is waste."""
        from src.jobs import get_job, put_job

        uri = put_job(JOBS_BUCKET, {"n": 1})
        get_job(uri)

        import src.jobs

        with patch.object(src.jobs._s3_client, "get_object") as mock_get:
            assert get_job(uri) == {"n": 1}
        mock_get.assert_not_called()

    def test_cache_is_bounded(self, jobs_bucket) -> None:
        """A warm container serves many executions; the cache must not grow."""
        import src.jobs
        from src.jobs import get_job, put_job

        for i in range(src.jobs._JOB_CACHE_MAX_ENTRIES + 4):
            get_job(put_job(JOBS_BUCKET, {"n": i}))

        assert len(src.jobs._job_cache) <= src.jobs._JOB_CACHE_MAX_ENTRIES

    def test_missing_bucket_is_a_configuration_error(self, jobs_bucket) -> None:
        from src.jobs import put_job

        with pytest.raises(ConfigurationError, match="JOBS_BUCKET"):
            put_job("", {"a": 1})

    def test_malformed_uri_rejected(self, jobs_bucket) -> None:
        from src.jobs import get_job

        with pytest.raises(ValidationError, match="Invalid job URI"):
            get_job("not-an-s3-uri")


# ---------------------------------------------------------------------------
# prepare
# ---------------------------------------------------------------------------


class TestPrepare:
    def test_returns_one_map_item_per_criterion(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        from src.handlers.prepare import handler

        result = handler(dict(SAMPLE_EVENT), lambda_ctx)

        # DefaultCriteria.balanced() has four dimensions.
        assert result["criteria_count"] == 4
        assert len(result["items"]) == 4
        assert [item["criterion_index"] for item in result["items"]] == [0, 1, 2, 3]
        assert all(item["job_uri"] == result["job_uri"] for item in result["items"])

    def test_only_a_uri_crosses_the_state_boundary(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        """Step Functions caps inter-state data at 256 KB; payloads stay in S3."""
        from src.handlers.prepare import handler

        result = handler(
            {"prompt": "x" * 400_000, "response": "y" * 400_000}, lambda_ctx
        )

        serialised = json.dumps(result)
        assert len(serialised) < 100_000
        assert "x" * 100 not in serialised
        assert result["job_uri"].startswith("s3://")

    def test_staged_payload_carries_everything_the_workers_need(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        from src.handlers.prepare import handler
        from src.jobs import get_job

        event = {
            **SAMPLE_EVENT,
            "system_prompt": "あなたは専門家です",
            "contexts": ["参考資料1", "参考資料2"],
            "prompt_descriptor": "operator note",
        }
        job = get_job(handler(event, lambda_ctx)["job_uri"])

        assert job["prompt"] == SAMPLE_EVENT["prompt"]
        assert job["system_prompt"] == "あなたは専門家です"
        assert job["contexts"] == ["参考資料1", "参考資料2"]
        assert job["prompt_descriptor"] == "operator note"
        assert job["has_prompt"] is True
        assert job["provider"] == "bedrock"
        assert len(job["criteria"]["criteria"]) == 4

    def test_rejects_the_same_events_as_direct_invoke(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        from src.handlers.prepare import handler

        with pytest.raises(ValidationError):
            handler({"prompt": "   ", "response": ""}, lambda_ctx)


# ---------------------------------------------------------------------------
# evaluate_criterion
# ---------------------------------------------------------------------------


class TestEvaluateCriterion:
    @staticmethod
    def _prepared(lambda_ctx, event=None) -> dict:
        from src.handlers.prepare import handler

        return handler(dict(event or SAMPLE_EVENT), lambda_ctx)

    def test_scores_only_the_indexed_criterion(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        from src.handlers.evaluate_criterion import handler

        prepared = self._prepared(lambda_ctx)
        provider = MagicMock()
        provider.complete.return_value = _criterion_json(4.5, "正確である")

        with patch("src.handlers.evaluate_criterion.get_provider", return_value=provider):
            result = handler(prepared["items"][1], lambda_ctx)

        assert provider.complete.call_count == 1
        assert result["name"] == "clarity"
        assert result["score"] == 4.5
        assert result["assessability"] == "assessed"
        assert result["reasoning"] == "正確である"

    def test_out_of_range_index_rejected(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        from src.handlers.evaluate_criterion import handler

        prepared = self._prepared(lambda_ctx)
        with pytest.raises(ValidationError, match="out of range"):
            handler({"job_uri": prepared["job_uri"], "criterion_index": 99}, lambda_ctx)

    def test_missing_job_uri_rejected(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        from src.handlers.evaluate_criterion import handler

        with pytest.raises(ValidationError, match="job_uri"):
            handler({"criterion_index": 0}, lambda_ctx)

    def test_boolean_is_not_accepted_as_an_index(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        """bool is a subclass of int; True must not silently mean index 1."""
        from src.handlers.evaluate_criterion import handler

        prepared = self._prepared(lambda_ctx)
        with pytest.raises(ValidationError, match="criterion_index"):
            handler(
                {"job_uri": prepared["job_uri"], "criterion_index": True}, lambda_ctx
            )

    def test_does_not_retry_internally(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        """Retries belong to the Map state, not to billed Lambda time."""
        from src.handler import ProviderError
        from src.handlers.evaluate_criterion import handler

        prepared = self._prepared(lambda_ctx)
        provider = MagicMock()
        provider.complete.side_effect = ProviderError("throttled")

        with patch("src.handlers.evaluate_criterion.get_provider", return_value=provider):
            with pytest.raises(ProviderError):
                handler(prepared["items"][0], lambda_ctx)

        assert provider.complete.call_count == 1


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------


class TestSummarize:
    def test_restores_criteria_file_ordering(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        """Map branches finish out of order; the rubric's order is what matters."""
        from src.handlers.prepare import handler as prepare
        from src.handlers.summarize import handler as summarize

        prepared = prepare(dict(SAMPLE_EVENT), lambda_ctx)
        shuffled = [
            {"name": "completeness", "assessability": "assessed", "score": 3.0,
             "reasoning": "d"},
            {"name": "accuracy", "assessability": "assessed", "score": 5.0,
             "reasoning": "a"},
            {"name": "helpfulness", "assessability": "assessed", "score": 4.0,
             "reasoning": "c"},
            {"name": "clarity", "assessability": "assessed", "score": 2.0,
             "reasoning": "b"},
        ]

        provider = MagicMock()
        provider.complete.return_value = "総評テキスト"

        with patch("src.handlers.summarize.get_provider", return_value=provider):
            result = summarize(
                {"job_uri": prepared["job_uri"], "results": shuffled}, lambda_ctx
            )

        assert list(result["criterion_reasoning"].keys()) == [
            "accuracy",
            "clarity",
            "helpfulness",
            "completeness",
        ]
        assert result["reasoning"] == "総評テキスト"

    def test_not_assessable_criteria_are_excluded_from_scores(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        from src.handlers.prepare import handler as prepare
        from src.handlers.summarize import handler as summarize

        prepared = prepare(dict(SAMPLE_EVENT), lambda_ctx)
        results = [
            {"name": "accuracy", "assessability": "assessed", "score": 4.0,
             "reasoning": "ok"},
            {"name": "clarity", "assessability": "not_assessable", "score": None,
             "reasoning": "missing role"},
        ]

        provider = MagicMock()
        provider.complete.return_value = "総評"

        with patch("src.handlers.summarize.get_provider", return_value=provider):
            result = summarize(
                {"job_uri": prepared["job_uri"], "results": results}, lambda_ctx
            )

        assert result["criterion_scores"] == {"accuracy": 4.0}
        assert result["criterion_assessability"]["clarity"] == "not_assessable"
        assert "clarity" in result["criterion_reasoning"]

    def test_empty_results_rejected(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        from src.handlers.prepare import handler as prepare
        from src.handlers.summarize import handler as summarize

        prepared = prepare(dict(SAMPLE_EVENT), lambda_ctx)
        with pytest.raises(ValidationError, match="results"):
            summarize({"job_uri": prepared["job_uri"], "results": []}, lambda_ctx)


# ---------------------------------------------------------------------------
# Contract equivalence
# ---------------------------------------------------------------------------


class TestWorkflowMatchesDirectInvoke:
    """Both entry points are public and share contracts/lambda-response.json."""

    def test_identical_response(self, jobs_bucket, bedrock_env, lambda_ctx) -> None:
        from src.handler import lambda_handler
        from src.handlers.evaluate_criterion import handler as evaluate_criterion
        from src.handlers.prepare import handler as prepare
        from src.handlers.summarize import handler as summarize

        def fresh_provider() -> MagicMock:
            provider = MagicMock()

            def complete(messages, model, timeout):  # noqa: ARG001
                text = messages[0]["content"]
                if "Per-Criterion Results" in text:
                    return "総評: 全体として良好。"
                return _criterion_json(4.0, "根拠テキスト")

            provider.complete.side_effect = complete
            return provider

        # Direct-invoke path.
        with patch("src.handler.get_provider", return_value=fresh_provider()):
            direct = lambda_handler(dict(SAMPLE_EVENT), lambda_ctx)

        # Workflow path, driven exactly as the state machine drives it.
        prepared = prepare(dict(SAMPLE_EVENT), lambda_ctx)
        with patch(
            "src.handlers.evaluate_criterion.get_provider",
            return_value=fresh_provider(),
        ):
            results = [
                evaluate_criterion(item, lambda_ctx) for item in prepared["items"]
            ]
        with patch(
            "src.handlers.summarize.get_provider", return_value=fresh_provider()
        ):
            workflow = summarize(
                {"job_uri": prepared["job_uri"], "results": results}, lambda_ctx
            )

        assert workflow == direct

    def test_both_paths_report_the_same_keys(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        """Guards the response schema in contracts/lambda-response.json."""
        from src.handlers.prepare import handler as prepare
        from src.handlers.summarize import handler as summarize

        prepared = prepare(dict(SAMPLE_EVENT), lambda_ctx)
        provider = MagicMock()
        provider.complete.return_value = "総評"

        with patch("src.handlers.summarize.get_provider", return_value=provider):
            result = summarize(
                {
                    "job_uri": prepared["job_uri"],
                    "results": [
                        {"name": "accuracy", "assessability": "assessed",
                         "score": 4.0, "reasoning": "r"}
                    ],
                },
                lambda_ctx,
            )

        assert set(result) == {
            "criterion_scores",
            "criterion_reasoning",
            "criterion_assessability",
            "reasoning",
            "judge_model",
            "provider",
        }
        assert "overall_score" not in result
