"""Tests for the Step Functions step handlers and the claim-check job store.

The workflow is the only entry point now that the single-Lambda path is gone, so
these tests own the response contract: the shape asserted here is what
``contracts/lambda-response.json`` describes and what callers depend on.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from src.errors import ConfigurationError, ValidationError

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


def _stored_pointers(prepared: dict, results) -> list[dict]:
    """Store per-criterion results in S3 and return the pointers summarize expects.

    The Map state hands summarize pointers, not reasoning text, so tests that
    drive summarize directly have to stage the results the same way
    evaluate_criterion would.
    """
    from src.jobs import put_result

    pointers = []
    for name, assessability, score, reasoning in results:
        payload = {
            "name": name,
            "assessability": assessability,
            "score": score,
            "reasoning": reasoning,
        }
        uri = put_result(JOBS_BUCKET, prepared["content_hash"], name, payload)
        pointers.append(
            {
                "name": name,
                "assessability": assessability,
                "score": score,
                "result_uri": uri,
            }
        )
    return pointers


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

    def test_malformed_events_are_rejected_before_any_model_call(
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

        # The reasoning text is offloaded so that state size stays independent
        # of the criteria count; only a pointer crosses the state boundary.
        assert "reasoning" not in result
        from src.jobs import get_result

        assert get_result(result["result_uri"])["reasoning"] == "正確である"

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
        from src.errors import ProviderError
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
        shuffled = _stored_pointers(
            prepared,
            [
                ("completeness", "assessed", 3.0, "d"),
                ("accuracy", "assessed", 5.0, "a"),
                ("helpfulness", "assessed", 4.0, "c"),
                ("clarity", "assessed", 2.0, "b"),
            ],
        )

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
        results = _stored_pointers(
            prepared,
            [
                ("accuracy", "assessed", 4.0, "ok"),
                ("clarity", "not_assessable", None, "missing role"),
            ],
        )

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
# Response contract
# ---------------------------------------------------------------------------


class TestResponseContract:
    """The workflow is the only entry point, so it owns the response contract.

    This validates the assembled response against the published JSON Schema
    rather than against a second implementation, which is what the old
    direct-invoke equivalence test did before that path was removed.
    """

    @staticmethod
    def _schema() -> dict:
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "contracts",
            "lambda-response.json",
        )
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def _run_workflow(self, lambda_ctx, event=None) -> dict:
        """Drive prepare -> evaluate_criterion(xN) -> summarize as the state machine does."""
        from src.handlers.evaluate_criterion import handler as evaluate_criterion
        from src.handlers.prepare import handler as prepare
        from src.handlers.summarize import handler as summarize

        def provider() -> MagicMock:
            mock = MagicMock()

            def complete(messages, model, timeout):  # noqa: ARG001
                text = messages[0]["content"]
                if "Per-Criterion Results" in text:
                    return "総評: 全体として良好。"
                return _criterion_json(4.0, "根拠テキスト")

            mock.complete.side_effect = complete
            return mock

        prepared = prepare(dict(event or SAMPLE_EVENT), lambda_ctx)
        with patch(
            "src.handlers.evaluate_criterion.get_provider", return_value=provider()
        ):
            results = [
                evaluate_criterion(item, lambda_ctx) for item in prepared["items"]
            ]
        with patch("src.handlers.summarize.get_provider", return_value=provider()):
            return summarize(
                {"job_uri": prepared["job_uri"], "results": results}, lambda_ctx
            )

    def test_response_validates_against_published_schema(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        import jsonschema

        jsonschema.validate(self._run_workflow(lambda_ctx), self._schema())

    def test_response_has_exactly_the_documented_keys(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        result = self._run_workflow(lambda_ctx)

        assert set(result) == {
            "criterion_scores",
            "criterion_reasoning",
            "criterion_assessability",
            "reasoning",
            "judge_model",
            "provider",
        }
        # Criteria are independent by design; no aggregate is computed.
        assert "overall_score" not in result

    def test_every_criterion_is_accounted_for(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        result = self._run_workflow(lambda_ctx)

        # DefaultCriteria.balanced() has four dimensions.
        assert len(result["criterion_assessability"]) == 4
        assert len(result["criterion_reasoning"]) == 4
        assert set(result["criterion_scores"]) <= set(result["criterion_assessability"])


# ---------------------------------------------------------------------------
# Content hashing and result offloading
# ---------------------------------------------------------------------------


class TestContentHash:
    """The hash decides what deduplicates, so what it covers is load-bearing."""

    @staticmethod
    def _payload(**overrides):
        base = {
            "prompt": "Q?",
            "response": "A.",
            "prompt_descriptor": None,
            "response_descriptor": None,
            "system_prompt": None,
            "contexts": None,
            "provider": "bedrock",
            "judge_model": "amazon.nova-lite-v1:0",
            "criteria": {"name": "c", "criteria": [{"name": "a", "description": "d"}]},
        }
        base.update(overrides)
        return base

    def test_identical_inputs_hash_identically(self) -> None:
        from src.jobs import compute_content_hash

        assert compute_content_hash(self._payload()) == compute_content_hash(
            self._payload()
        )

    def test_key_order_does_not_matter(self) -> None:
        """Payloads are built in different orders in different code paths."""
        from src.jobs import compute_content_hash

        forward = self._payload()
        reversed_order = dict(reversed(list(forward.items())))
        assert compute_content_hash(forward) == compute_content_hash(reversed_order)

    def test_job_identity_is_excluded(self) -> None:
        """A per-execution UUID must not enter the hash, or nothing dedupes."""
        from src.jobs import compute_content_hash

        assert compute_content_hash(
            self._payload(job_id="uuid-1")
        ) == compute_content_hash(self._payload(job_id="uuid-2"))

    @pytest.mark.parametrize(
        "field,value",
        [
            ("prompt", "different"),
            ("response", "different"),
            ("system_prompt", "be strict"),
            ("contexts", ["extra"]),
            ("judge_model", "amazon.nova-pro-v1:0"),
            ("provider", "anthropic"),
            ("prompt_descriptor", "note"),
        ],
    )
    def test_outcome_bearing_fields_change_the_hash(
        self, field: str, value: object
    ) -> None:
        from src.jobs import compute_content_hash

        assert compute_content_hash(self._payload()) != compute_content_hash(
            self._payload(**{field: value})
        )

    def test_changing_criteria_changes_the_hash(self) -> None:
        from src.jobs import compute_content_hash

        other = {"name": "c", "criteria": [{"name": "b", "description": "d"}]}
        assert compute_content_hash(self._payload()) != compute_content_hash(
            self._payload(criteria=other)
        )

    def test_prepare_stages_the_hash(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        from src.handlers.prepare import handler
        from src.jobs import get_job

        prepared = handler(dict(SAMPLE_EVENT), lambda_ctx)
        assert prepared["content_hash"]
        assert get_job(prepared["job_uri"])["content_hash"] == prepared["content_hash"]

    def test_same_submission_hashes_the_same_across_executions(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        """Two executions of identical input must agree, or the idempotency
        layer would never see a repeat."""
        from src.handlers.prepare import handler

        first = handler(dict(SAMPLE_EVENT), lambda_ctx)
        second = handler(dict(SAMPLE_EVENT), lambda_ctx)

        assert first["job_uri"] != second["job_uri"]
        assert first["content_hash"] == second["content_hash"]


class TestResultOffloading:
    def test_result_keys_are_deterministic(self, jobs_bucket) -> None:
        """A retried criterion overwrites its object rather than orphaning one."""
        from src.jobs import put_result

        first = put_result(JOBS_BUCKET, "hash1", "accuracy", {"n": 1})
        second = put_result(JOBS_BUCKET, "hash1", "accuracy", {"n": 2})

        assert first == second

    def test_different_criteria_get_different_keys(self, jobs_bucket) -> None:
        from src.jobs import put_result

        assert put_result(JOBS_BUCKET, "h", "accuracy", {}) != put_result(
            JOBS_BUCKET, "h", "clarity", {}
        )

    def test_round_trip_preserves_japanese_reasoning(self, jobs_bucket) -> None:
        from src.jobs import get_result, put_result

        payload = {"name": "a", "reasoning": "事実の正確性は高い。", "score": 4.0}
        assert get_result(put_result(JOBS_BUCKET, "h", "a", payload)) == payload

    def test_batch_fetch_preserves_order(self, jobs_bucket) -> None:
        """summarize relies on this to line results up with criteria."""
        from src.jobs import get_results, put_result

        uris = [put_result(JOBS_BUCKET, "h", f"c{i}", {"i": i}) for i in range(12)]
        assert [r["i"] for r in get_results(uris)] == list(range(12))

    def test_batch_fetch_handles_empty_and_single(self, jobs_bucket) -> None:
        from src.jobs import get_results, put_result

        assert get_results([]) == []
        uri = put_result(JOBS_BUCKET, "h", "only", {"i": 0})
        assert get_results([uri]) == [{"i": 0}]

    def test_missing_result_is_not_silently_skipped(self, jobs_bucket) -> None:
        """Dropping a result would understate the rubric while looking complete."""
        from src.errors import LlmJudgeError
        from src.jobs import get_results, put_result

        good = put_result(JOBS_BUCKET, "h", "a", {"i": 0})
        with pytest.raises(LlmJudgeError):
            get_results([good, f"s3://{JOBS_BUCKET}/results/h/absent.json"])

    def test_state_payload_stays_small_regardless_of_reasoning_length(
        self, jobs_bucket, bedrock_env, lambda_ctx
    ) -> None:
        """The 256 KB state limit is why reasoning is offloaded at all."""
        from src.handlers.evaluate_criterion import handler
        from src.handlers.prepare import handler as prepare

        prepared = prepare(dict(SAMPLE_EVENT), lambda_ctx)
        provider = MagicMock()
        provider.complete.return_value = _criterion_json(4.0, "根" * 50_000)

        with patch(
            "src.handlers.evaluate_criterion.get_provider", return_value=provider
        ):
            result = handler(prepared["items"][0], lambda_ctx)

        assert len(json.dumps(result)) < 1_000


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


IDEMPOTENCY_TABLE = "llm-judge-idempotency-test"


@pytest.fixture
def idempotency_table(monkeypatch: pytest.MonkeyPatch):
    """A DynamoDB table standing in for the idempotency store."""
    with mock_aws():
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName=IDEMPOTENCY_TABLE,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        monkeypatch.setenv("IDEMPOTENCY_TABLE", IDEMPOTENCY_TABLE)
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        yield dynamodb


class TestIdempotencyWiring:
    def test_disabled_without_a_table(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Local runs and tests must not require DynamoDB."""
        monkeypatch.delenv("IDEMPOTENCY_TABLE", raising=False)

        from src.idempotency import idempotent_criterion_call, is_enabled

        assert is_enabled() is False

        def fn(*, payload):
            return payload["n"]

        # Pass-through: same object back, no wrapper.
        assert idempotent_criterion_call(fn) is fn

    def test_enabled_when_a_table_is_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("IDEMPOTENCY_TABLE", "some-table")

        from src.idempotency import is_enabled

        assert is_enabled() is True

    def test_key_includes_content_criterion_and_model(self) -> None:
        """All three must participate, or different work would collide."""
        from src.idempotency import build_key

        base = build_key("hash", "accuracy", "model-a")
        assert base != build_key("other", "accuracy", "model-a")
        assert base != build_key("hash", "clarity", "model-a")
        assert base != build_key("hash", "accuracy", "model-b")
        assert base == build_key("hash", "accuracy", "model-a")

    def test_blank_table_name_is_treated_as_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("IDEMPOTENCY_TABLE", "   ")

        from src.idempotency import is_enabled

        assert is_enabled() is False


class TestIdempotentCriterionEvaluation:
    """The judge call is the expensive part; a repeat must not pay for it twice."""

    @staticmethod
    def _reload_handler():
        """Re-import so the decorator re-reads IDEMPOTENCY_TABLE."""
        import importlib

        import src.handlers.evaluate_criterion as module

        return importlib.reload(module)

    def test_repeated_criterion_does_not_call_the_model_again(
        self, jobs_bucket, idempotency_table, bedrock_env, lambda_ctx
    ) -> None:
        from src.handlers.prepare import handler as prepare

        module = self._reload_handler()
        prepared = prepare(dict(SAMPLE_EVENT), lambda_ctx)

        provider = MagicMock()
        provider.complete.return_value = _criterion_json(4.0, "根拠")

        with patch.object(module, "get_provider", return_value=provider):
            first = module.handler(prepared["items"][0], lambda_ctx)
            second = module.handler(prepared["items"][0], lambda_ctx)

        assert provider.complete.call_count == 1, (
            "the second evaluation of the same criterion called the model again"
        )
        assert first == second

    def test_identical_resubmission_reuses_the_stored_result(
        self, jobs_bucket, idempotency_table, bedrock_env, lambda_ctx
    ) -> None:
        """A different execution of the same content must still deduplicate."""
        from src.handlers.prepare import handler as prepare

        module = self._reload_handler()
        first_job = prepare(dict(SAMPLE_EVENT), lambda_ctx)
        second_job = prepare(dict(SAMPLE_EVENT), lambda_ctx)
        assert first_job["job_uri"] != second_job["job_uri"]

        provider = MagicMock()
        provider.complete.return_value = _criterion_json(4.0, "根拠")

        with patch.object(module, "get_provider", return_value=provider):
            module.handler(first_job["items"][0], lambda_ctx)
            module.handler(second_job["items"][0], lambda_ctx)

        assert provider.complete.call_count == 1

    def test_different_criteria_are_evaluated_separately(
        self, jobs_bucket, idempotency_table, bedrock_env, lambda_ctx
    ) -> None:
        from src.handlers.prepare import handler as prepare

        module = self._reload_handler()
        prepared = prepare(dict(SAMPLE_EVENT), lambda_ctx)

        provider = MagicMock()
        provider.complete.return_value = _criterion_json(4.0, "根拠")

        with patch.object(module, "get_provider", return_value=provider):
            for item in prepared["items"]:
                module.handler(item, lambda_ctx)

        assert provider.complete.call_count == len(prepared["items"])

    def test_without_a_table_every_call_reaches_the_model(
        self, jobs_bucket, bedrock_env, lambda_ctx, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Degrading to 'always evaluate' is correct; returning stale is not."""
        monkeypatch.delenv("IDEMPOTENCY_TABLE", raising=False)
        from src.handlers.prepare import handler as prepare

        module = self._reload_handler()
        prepared = prepare(dict(SAMPLE_EVENT), lambda_ctx)

        provider = MagicMock()
        provider.complete.return_value = _criterion_json(4.0, "根拠")

        with patch.object(module, "get_provider", return_value=provider):
            module.handler(prepared["items"][0], lambda_ctx)
            module.handler(prepared["items"][0], lambda_ctx)

        assert provider.complete.call_count == 2
