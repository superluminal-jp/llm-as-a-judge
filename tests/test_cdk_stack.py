"""Infrastructure assertions for :class:`cdk.stack.LlmJudgeStack`.

These tests synthesise the stack in-process with ``aws_cdk.assertions`` and
assert the properties that matter operationally: least-privilege IAM, bounded
log retention, a dead-letter queue, tracing, and concurrency limits.

Docker is not required: the ``aws:cdk:bundling-stacks`` context key is set to an
empty list, which tells the CDK to skip asset bundling. That key cannot be
passed on the ``cdk`` CLI (the CLI rejects user context prefixed with ``aws:``)
but is accepted when supplied programmatically to :class:`~aws_cdk.App`.
"""

from __future__ import annotations

import json
import os
import sys

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

# cdk/app.py imports `stack` as a top-level module, so cdk/ must be importable.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "cdk"))

from stack import LlmJudgeStack  # noqa: E402


DEFAULT_MODELS = ["jp.anthropic.claude-sonnet-4-6", "amazon.nova-lite-v1:0"]
DEFAULT_PROFILE_REGIONS = ["ap-northeast-1", "ap-northeast-3"]


def _synth(**overrides) -> Template:
    """Synthesise LlmJudgeStack and return its assertions Template."""
    app = cdk.App(context={"aws:cdk:bundling-stacks": []})
    kwargs = {
        "environment_name": "dev",
        "default_provider": "bedrock",
        "bedrock_model": "jp.anthropic.claude-sonnet-4-6",
        "bedrock_allowed_models": list(DEFAULT_MODELS),
        "bedrock_inference_profile_regions": list(DEFAULT_PROFILE_REGIONS),
        "criteria_bucket_arn": "",
    }
    kwargs.update(overrides)
    stack = LlmJudgeStack(
        app,
        "LlmJudgeStack-test",
        env=cdk.Environment(account="111122223333", region="ap-northeast-1"),
        **kwargs,
    )
    return Template.from_stack(stack)


@pytest.fixture(scope="module")
def template() -> Template:
    """Synthesised template for the default (stack-managed bucket) configuration."""
    return _synth()


def _judge_role_statements(template: Template) -> list[dict]:
    """Return the IAM statements attached to the judge function's execution role.

    The stack also synthesises a role for the S3 BucketDeployment custom
    resource; assertions about least privilege must not accidentally inspect it.
    """
    rendered = template.to_json()["Resources"]
    role_logical_ids = {
        logical_id
        for logical_id, resource in rendered.items()
        if resource["Type"] == "AWS::IAM::Role"
        and logical_id.startswith("LlmJudgeFunctionServiceRole")
    }
    assert role_logical_ids, "judge function execution role not found"

    statements: list[dict] = []
    for resource in rendered.values():
        if resource["Type"] != "AWS::IAM::Policy":
            continue
        refs = {
            role.get("Ref")
            for role in resource["Properties"].get("Roles", [])
            if isinstance(role, dict)
        }
        if refs & role_logical_ids:
            statements.extend(resource["Properties"]["PolicyDocument"]["Statement"])
    return statements


# ---------------------------------------------------------------------------
# IAM — least privilege
# ---------------------------------------------------------------------------


class TestBedrockIam:
    """The Bedrock policy must name specific models, never a wildcard."""

    def test_no_wildcard_foundation_model_resource(self, template: Template) -> None:
        rendered = template.to_json()
        assert "foundation-model/*" not in str(rendered), (
            "Bedrock policy still grants every foundation model; it must be "
            "scoped to bedrock_allowed_models."
        )

    def test_grants_inference_profile_arn(self, template: Template) -> None:
        """Cross-region profile IDs need the inference-profile ARN itself."""
        rendered = str(template.to_json())
        assert (
            "inference-profile/jp.anthropic.claude-sonnet-4-6" in rendered
        ), "Missing inference-profile ARN for the jp. cross-region profile."

    def test_grants_underlying_model_in_every_routed_region(
        self, template: Template
    ) -> None:
        """Profile invocation also needs the base model in each routed region."""
        rendered = str(template.to_json())
        for region in DEFAULT_PROFILE_REGIONS:
            assert (
                f"bedrock:{region}::foundation-model/anthropic.claude-sonnet-4-6"
                in rendered
            ), f"Missing foundation-model grant in routed region {region}."

    def test_grants_plain_model_id_without_profile_arn(
        self, template: Template
    ) -> None:
        """A non-prefixed model ID resolves to a foundation-model ARN only."""
        rendered = str(template.to_json())
        assert "foundation-model/amazon.nova-lite-v1:0" in rendered
        assert "inference-profile/amazon.nova-lite-v1:0" not in rendered

    def test_invoke_model_action_present(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Sid": "BedrockInvokeConfiguredModels",
                                    "Action": Match.array_with(
                                        ["bedrock:InvokeModel"]
                                    ),
                                    "Effect": "Allow",
                                }
                            )
                        ]
                    )
                }
            },
        )


class TestS3Iam:
    """Criteria access is object-level read only."""

    def test_get_object_only(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Sid": "S3GetCriteriaObject",
                                    "Action": "s3:GetObject",
                                    "Effect": "Allow",
                                }
                            )
                        ]
                    )
                }
            },
        )

    def test_judge_role_gets_no_bucket_level_access(self, template: Template) -> None:
        """The judge function reads objects only.

        Scoped to the function's own role: the BucketDeployment custom resource
        legitimately holds broader access to the same bucket, so a whole-template
        string search would pass vacuously.
        """
        for statement in _judge_role_statements(template):
            actions = statement["Action"]
            actions = [actions] if isinstance(actions, str) else actions
            for action in actions:
                assert not str(action).startswith("s3:List"), (
                    f"judge role must not hold bucket-level S3 access: {action}"
                )
                assert not str(action).startswith("s3:Put"), (
                    f"judge role must not hold S3 write access: {action}"
                )


# ---------------------------------------------------------------------------
# Lambda configuration
# ---------------------------------------------------------------------------


class TestLambdaConfiguration:
    def test_timeout_allows_full_criteria_sweep(self, template: Template) -> None:
        """60s was too short for the 10-criterion file; 300s is the new floor."""
        template.has_resource_properties(
            "AWS::Lambda::Function",
            Match.object_like({"Timeout": 300}),
        )

    def test_runs_on_arm64(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::Lambda::Function",
            Match.object_like({"Architectures": ["arm64"]}),
        )

    def test_tracing_active(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::Lambda::Function",
            Match.object_like({"TracingConfig": {"Mode": "Active"}}),
        )

    def test_reserved_concurrency_set(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::Lambda::Function",
            Match.object_like({"ReservedConcurrentExecutions": 10}),
        )

    def test_dead_letter_queue_attached(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::Lambda::Function",
            Match.object_like({"DeadLetterConfig": Match.any_value()}),
        )
        template.resource_count_is("AWS::SQS::Queue", 1)

    def test_json_logging_with_levels(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::Lambda::Function",
            Match.object_like(
                {
                    "LoggingConfig": Match.object_like(
                        {
                            "LogFormat": "JSON",
                            "ApplicationLogLevel": "INFO",
                            "SystemLogLevel": "WARN",
                        }
                    )
                }
            ),
        )

    def test_environment_variables_carry_no_api_keys(
        self, template: Template
    ) -> None:
        """API keys must come from Secrets Manager, never the function env."""
        functions = template.find_resources("AWS::Lambda::Function")
        for resource in functions.values():
            env = resource["Properties"].get("Environment", {}).get("Variables", {})
            assert "ANTHROPIC_API_KEY" not in env
            assert "OPENAI_API_KEY" not in env

    def test_environment_encrypted_with_cmk(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::Lambda::Function",
            Match.object_like({"KmsKeyArn": Match.any_value()}),
        )

    def test_secret_name_passed_to_runtime(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::Lambda::Function",
            Match.object_like(
                {
                    "Environment": {
                        "Variables": Match.object_like(
                            {"API_KEYS_SECRET_NAME": Match.any_value()}
                        )
                    }
                }
            ),
        )


# ---------------------------------------------------------------------------
# Logs, alarms, and supporting resources
# ---------------------------------------------------------------------------


class TestObservability:
    def test_log_group_retention_is_bounded(self, template: Template) -> None:
        """Without an explicit group, Lambda creates one that never expires."""
        template.has_resource_properties(
            "AWS::Logs::LogGroup",
            Match.object_like({"RetentionInDays": 30}),
        )

    def test_production_uses_longer_retention(self) -> None:
        prod = _synth(environment_name="prod")
        prod.has_resource_properties(
            "AWS::Logs::LogGroup",
            Match.object_like({"RetentionInDays": 90}),
        )

    def test_alarms_exist(self, template: Template) -> None:
        template.resource_count_is("AWS::CloudWatch::Alarm", 4)

    def test_alarms_notify_sns(self, template: Template) -> None:
        alarms = template.find_resources("AWS::CloudWatch::Alarm")
        assert alarms, "no alarms synthesised"
        for resource in alarms.values():
            assert resource["Properties"].get("AlarmActions"), (
                "alarm has no SNS action attached"
            )

    def test_dashboard_created(self, template: Template) -> None:
        template.resource_count_is("AWS::CloudWatch::Dashboard", 1)


class TestCdkNagCompliance:
    """The AWS Solutions rule pack must report no unsuppressed findings.

    Suppressions live in cdk/stack.py and each carries a written reason; this
    test fails when a change introduces a finding that nobody has justified.
    """

    def test_no_unsuppressed_findings(self, tmp_path) -> None:
        import glob

        from cdk_nag import AwsSolutionsChecks, NagReportFormat

        app = cdk.App(
            outdir=str(tmp_path), context={"aws:cdk:bundling-stacks": []}
        )
        LlmJudgeStack(
            app,
            "LlmJudgeStack-dev",
            env=cdk.Environment(account="111122223333", region="ap-northeast-1"),
            environment_name="dev",
            default_provider="bedrock",
            bedrock_model="jp.anthropic.claude-sonnet-4-6",
            bedrock_allowed_models=list(DEFAULT_MODELS),
            bedrock_inference_profile_regions=list(DEFAULT_PROFILE_REGIONS),
            criteria_bucket_arn="",
        )
        cdk.Aspects.of(app).add(
            AwsSolutionsChecks(
                verbose=True,
                reports=True,
                report_formats=[NagReportFormat.JSON],
            )
        )
        app.synth()

        reports = glob.glob(str(tmp_path / "*NagReport.json"))
        assert reports, "cdk-nag produced no report"

        with open(reports[0], encoding="utf-8") as handle:
            lines = json.load(handle)["lines"]

        findings = [
            f"{line['ruleId']} on {line['resourceId']}"
            for line in lines
            if line["compliance"] == "Non-Compliant"
        ]
        assert not findings, "unsuppressed cdk-nag findings:\n" + "\n".join(findings)

        # Guard against the opposite failure: a blanket suppression that
        # silences the whole rule pack.
        assert any(line["compliance"] == "Compliant" for line in lines)


class TestSupportingResources:
    def test_secret_created_with_cmk(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::SecretsManager::Secret",
            Match.object_like({"KmsKeyId": Match.any_value()}),
        )

    def test_kms_key_rotates(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::KMS::Key",
            Match.object_like({"EnableKeyRotation": True}),
        )

    def test_judge_role_can_encrypt_for_the_dlq(self, template: Template) -> None:
        """kms:Decrypt alone is not enough to write to a CMK-encrypted queue."""
        granted: set[str] = set()
        for statement in _judge_role_statements(template):
            actions = statement["Action"]
            actions = [actions] if isinstance(actions, str) else actions
            granted.update(str(a) for a in actions)
        assert any(a.startswith("kms:GenerateDataKey") for a in granted), (
            "judge role cannot generate a data key, so DLQ delivery would fail "
            f"silently. Granted KMS actions: {sorted(a for a in granted if 'kms' in a)}"
        )

    def test_cloudwatch_can_publish_to_encrypted_alarm_topic(
        self, template: Template
    ) -> None:
        """Alarms on a CMK-encrypted topic need an explicit key grant."""
        keys = template.find_resources("AWS::KMS::Key")
        statements = [
            statement
            for key in keys.values()
            for statement in key["Properties"]["KeyPolicy"]["Statement"]
        ]
        matching = [
            s
            for s in statements
            if s.get("Principal", {}).get("Service") == "cloudwatch.amazonaws.com"
        ]
        assert matching, (
            "CloudWatch has no key access; alarm notifications to the encrypted "
            "SNS topic would be dropped."
        )

    def test_dlq_is_encrypted_and_tls_only(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::SQS::Queue",
            Match.object_like({"KmsMasterKeyId": Match.any_value()}),
        )
        policies = template.find_resources("AWS::SQS::QueuePolicy")
        assert "aws:SecureTransport" in str(policies)

    def test_stack_creates_hardened_criteria_bucket_by_default(
        self, template: Template
    ) -> None:
        template.has_resource_properties(
            "AWS::S3::Bucket",
            Match.object_like(
                {
                    "PublicAccessBlockConfiguration": {
                        "BlockPublicAcls": True,
                        "BlockPublicPolicy": True,
                        "IgnorePublicAcls": True,
                        "RestrictPublicBuckets": True,
                    },
                    "VersioningConfiguration": {"Status": "Enabled"},
                }
            ),
        )

    def test_existing_bucket_arn_is_imported_not_created(self) -> None:
        imported = _synth(
            criteria_bucket_arn="arn:aws:s3:::existing-criteria-bucket"
        )
        buckets = imported.find_resources("AWS::S3::Bucket")
        assert buckets == {}, "an existing bucket ARN must not create a new bucket"
        assert "existing-criteria-bucket" in str(imported.to_json())
