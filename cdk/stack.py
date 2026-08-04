"""CDK stack definition for LLM-as-a-Judge Lambda deployment.

Deploys the evaluation Lambda together with the supporting resources it needs to
be operable in production:

* **Lambda function** — Python 3.12 on ARM64 (Graviton), explicit log group,
  JSON structured logging, active X-Ray tracing, reserved concurrency, and an
  SQS dead-letter queue for failed asynchronous invocations.
* **IAM** — ``bedrock:InvokeModel`` scoped to the *specific* model IDs and
  cross-region inference profiles configured in ``config/parameters.json``,
  rather than ``arn:aws:bedrock:*::foundation-model/*``.
* **Secrets Manager** — a single JSON secret holding the Anthropic and OpenAI
  API keys, read lazily at runtime through Powertools ``parameters``.
* **KMS** — one customer-managed key encrypting the Lambda environment
  variables, the dead-letter queue, the alarm topic, and the API-key secret.
* **S3** — the criteria bucket, either created by this stack (encrypted,
  versioned, TLS-only, public access blocked) or imported from an existing ARN.
* **CloudWatch** — alarms on errors, throttles, duration, and DLQ depth, plus a
  dashboard, all notifying an SNS topic.

Cross-region inference profiles
    Bedrock model IDs carrying a region prefix (``jp.``, ``us.``, ``eu.``,
    ``apac.``, …) are *inference profile* IDs, not foundation-model IDs.
    Invoking one requires ``bedrock:InvokeModel`` on **both** the inference
    profile ARN in the calling region **and** the underlying foundation-model
    ARN in every region the profile routes to. Granting only the latter — as
    this stack previously did — fails with ``AccessDeniedException``.
    :meth:`LlmJudgeStack._bedrock_model_resources` builds both sets of ARNs from
    ``bedrock_allowed_models`` and ``bedrock_inference_profile_regions``.
"""

from __future__ import annotations

import json
import os

import aws_cdk as cdk
import aws_cdk.aws_cloudwatch as cloudwatch
import aws_cdk.aws_cloudwatch_actions as cw_actions
import aws_cdk.aws_iam as iam
import aws_cdk.aws_kms as kms
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_logs as logs
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_s3_deployment as s3_deployment
import aws_cdk.aws_secretsmanager as secretsmanager
import aws_cdk.aws_sns as sns
import aws_cdk.aws_sqs as sqs
from cdk_nag import NagSuppressions
from constructs import Construct

# Region prefixes that identify a Bedrock cross-region inference profile ID.
# See the "Cross-region inference" section of the Amazon Bedrock User Guide.
_INFERENCE_PROFILE_PREFIXES = frozenset(
    {"us", "us-gov", "eu", "apac", "jp", "au", "ca"}
)

# Lambda timeout. Sized for the worst case in this repository: the 10-criterion
# AISI criteria file evaluated MAX_PARALLEL_CRITERIA at a time, plus the final
# summary call. Must stay comfortably above REQUEST_TIMEOUT * number of waves.
_LAMBDA_TIMEOUT_SEC = 300

# Per-request Bedrock/HTTP timeout handed to the runtime as REQUEST_TIMEOUT.
# Kept well below _LAMBDA_TIMEOUT_SEC so the provider's own timeout fires first
# and produces a diagnosable ProviderError instead of a Lambda hard kill.
_REQUEST_TIMEOUT_SEC = 60

# Upper bound on concurrent judge LLM calls within a single invocation. Caps the
# fan-out that criteria count would otherwise dictate, protecting Bedrock quota.
_MAX_PARALLEL_CRITERIA = 5


class LlmJudgeStack(cdk.Stack):
    """CloudFormation stack for the LLM-as-a-Judge Lambda function.

    Configuration is driven by ``config/parameters.json`` (passed in as keyword
    arguments by :mod:`cdk.app`) and can be overridden per-deployment with CDK
    context values (``--context key=value``) for the keys listed below.

    Context keys (override the corresponding keyword argument when non-empty):

        default_provider (str):     LLM provider used when the Lambda event does
                                    not specify one. Defaults to ``"bedrock"``.
        bedrock_model (str):        Default Bedrock judge model / inference
                                    profile ID.
        criteria_bucket_arn (str):  ARN of an existing S3 bucket holding
                                    criteria JSON files. When empty, this stack
                                    creates and manages the bucket itself.

    Args:
        scope:            CDK construct scope (the :class:`~aws_cdk.App`).
        construct_id:     Logical ID for this stack.
        environment_name: Deployment environment label (``dev`` / ``prod``).
                          Used in resource names and log retention policy.
        default_provider: Default LLM provider.
        bedrock_model:    Default Bedrock model or inference profile ID.
        bedrock_allowed_models: Every Bedrock model/profile ID the function is
                          permitted to invoke. Defaults to
                          ``[bedrock_model]``.
        bedrock_inference_profile_regions: Regions a cross-region inference
                          profile routes to. Foundation-model ARNs are granted
                          in each. Defaults to the stack region.
        criteria_bucket_arn: ARN of an existing criteria bucket, or empty to
                          have this stack create one.
        **kwargs:         Forwarded to :class:`~aws_cdk.Stack`.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        environment_name: str = "dev",
        default_provider: str | None = None,
        bedrock_model: str | None = None,
        bedrock_allowed_models: list[str] | None = None,
        bedrock_inference_profile_regions: list[str] | None = None,
        criteria_bucket_arn: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        def _first_non_empty(*vals: object) -> str | None:
            for v in vals:
                if v is None:
                    continue
                s = str(v).strip()
                if s:
                    return s
            return None

        environment_name = _first_non_empty(environment_name) or "dev"
        is_production = environment_name.lower() in ("prod", "production")

        default_provider = (
            _first_non_empty(
                self.node.try_get_context("default_provider"),
                default_provider,
            )
            or "bedrock"
        )
        bedrock_model = (
            _first_non_empty(
                self.node.try_get_context("bedrock_model"),
                bedrock_model,
            )
            or "jp.anthropic.claude-sonnet-4-6"
        )
        criteria_bucket_arn = (
            _first_non_empty(
                self.node.try_get_context("criteria_bucket_arn"),
                criteria_bucket_arn,
            )
            or ""
        )

        allowed_models = [m for m in (bedrock_allowed_models or []) if m]
        if bedrock_model not in allowed_models:
            allowed_models.append(bedrock_model)

        profile_regions = [r for r in (bedrock_inference_profile_regions or []) if r]

        resource_prefix = f"llm-judge-{environment_name}"

        # -----------------------------------------------------------------
        # KMS — one customer-managed key for every encrypted resource here
        # -----------------------------------------------------------------

        encryption_key = kms.Key(
            self,
            "LlmJudgeKey",
            alias=f"alias/{resource_prefix}",
            description=(
                "Encrypts LLM-as-a-Judge Lambda environment variables, API key "
                "secret, dead-letter queue, and alarm topic."
            ),
            enable_key_rotation=True,
            removal_policy=(
                cdk.RemovalPolicy.RETAIN if is_production else cdk.RemovalPolicy.DESTROY
            ),
        )

        # -----------------------------------------------------------------
        # Secrets Manager — Anthropic / OpenAI API keys
        # -----------------------------------------------------------------
        # Created with empty placeholder values so that the stack can be
        # deployed without any secret material in source control. Populate it
        # after deployment, e.g.:
        #   aws secretsmanager put-secret-value --secret-id <name> \
        #     --secret-string '{"ANTHROPIC_API_KEY":"sk-ant-...","OPENAI_API_KEY":""}'
        # Bedrock needs no entry here — it authenticates via the execution role.

        api_keys_secret = secretsmanager.Secret(
            self,
            "LlmJudgeApiKeys",
            secret_name=f"{resource_prefix}/api-keys",
            description=(
                "Anthropic and OpenAI API keys for the LLM-as-a-Judge judge "
                "models. Not required when using Amazon Bedrock."
            ),
            encryption_key=encryption_key,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                # Placeholder keys start empty; the generated field exists only
                # because Secrets Manager requires something to generate.
                secret_string_template=json.dumps(
                    {"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": ""}
                ),
                generate_string_key="unused_generated_value",
            ),
            removal_policy=(
                cdk.RemovalPolicy.RETAIN if is_production else cdk.RemovalPolicy.DESTROY
            ),
        )

        # -----------------------------------------------------------------
        # S3 — criteria bucket (created here unless an existing ARN was given)
        # -----------------------------------------------------------------

        criteria_bucket: s3.IBucket
        stack_manages_bucket = not criteria_bucket_arn

        if stack_manages_bucket:
            # Criteria define how submissions are scored, so who read or changed
            # them is auditable information. Server access logs go to a separate
            # bucket — a bucket cannot usefully log to itself.
            access_logs_bucket = s3.Bucket(
                self,
                "CriteriaAccessLogsBucket",
                encryption=s3.BucketEncryption.S3_MANAGED,
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                enforce_ssl=True,
                versioned=False,
                lifecycle_rules=[
                    s3.LifecycleRule(
                        id="ExpireAccessLogs",
                        expiration=cdk.Duration.days(365 if is_production else 90),
                    )
                ],
                removal_policy=cdk.RemovalPolicy.RETAIN,
            )
            criteria_bucket = s3.Bucket(
                self,
                "CriteriaBucket",
                encryption=s3.BucketEncryption.S3_MANAGED,
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                enforce_ssl=True,
                versioned=True,
                server_access_logs_bucket=access_logs_bucket,
                server_access_logs_prefix="criteria-bucket/",
                removal_policy=cdk.RemovalPolicy.RETAIN,
            )
            # Ship the criteria JSON files that live in this repository.
            s3_deployment.BucketDeployment(
                self,
                "CriteriaDeployment",
                sources=[
                    s3_deployment.Source.asset(
                        os.path.join(
                            os.path.dirname(os.path.abspath(__file__)), "..", "criteria"
                        ),
                        exclude=["README.md"],
                    )
                ],
                destination_bucket=criteria_bucket,
                destination_key_prefix="criteria",
                retain_on_delete=True,
            )
        else:
            criteria_bucket = s3.Bucket.from_bucket_arn(
                self, "CriteriaBucket", criteria_bucket_arn
            )

        # -----------------------------------------------------------------
        # SQS — dead-letter queue for failed asynchronous invocations
        # -----------------------------------------------------------------

        dead_letter_queue = sqs.Queue(
            self,
            "LlmJudgeDlq",
            queue_name=f"{resource_prefix}-dlq",
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=encryption_key,
            enforce_ssl=True,
            retention_period=cdk.Duration.days(14),
            removal_policy=(
                cdk.RemovalPolicy.RETAIN if is_production else cdk.RemovalPolicy.DESTROY
            ),
        )

        # -----------------------------------------------------------------
        # CloudWatch Logs — explicit group so retention is bounded
        # -----------------------------------------------------------------
        # Without this the Lambda service lazily creates the group with
        # "Never expire" retention, which accrues storage cost indefinitely.

        log_group = logs.LogGroup(
            self,
            "LlmJudgeLogGroup",
            log_group_name=f"/aws/lambda/{resource_prefix}",
            retention=(
                logs.RetentionDays.THREE_MONTHS
                if is_production
                else logs.RetentionDays.ONE_MONTH
            ),
            removal_policy=(
                cdk.RemovalPolicy.RETAIN if is_production else cdk.RemovalPolicy.DESTROY
            ),
        )

        # -----------------------------------------------------------------
        # Lambda function
        # -----------------------------------------------------------------

        function = lambda_.Function(
            self,
            "LlmJudgeFunction",
            function_name=resource_prefix,
            runtime=lambda_.Runtime.PYTHON_3_13,
            # ARM64/Graviton: cheaper per GB-second and equally suited to this
            # I/O-bound workload, which spends its time waiting on model APIs.
            architecture=lambda_.Architecture.ARM_64,
            # Handler path: src.handler module -> lambda_handler function.
            # The src/ package is preserved in the bundle so that intra-package
            # imports (from src.config, from src.criteria, ...) resolve correctly.
            handler="src.handler.lambda_handler",
            # Bundle src/ as a package alongside pip-installed dependencies
            # (requires Docker for cdk synth / deploy).
            # Path is relative to cdk.json (repo root), not the cdk/ package dir.
            # `exclude` keeps unrelated files out of the asset hash so that
            # editing docs or tests does not trigger a Lambda redeploy.
            code=lambda_.Code.from_asset(
                ".",
                exclude=[
                    ".git",
                    ".github",
                    "cdk",
                    "cdk.out",
                    "criteria",
                    "docs",
                    "examples",
                    "contracts",
                    "scripts",
                    "tests",
                    ".venv",
                    "venv",
                    "**/__pycache__",
                    "**/*.pyc",
                ],
                bundling=cdk.BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_13.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        (
                            # Install to /tmp first: pip -t onto a Docker volume can hit
                            # cross-device rename / EPERM on Colima (macOS).
                            "pip install --no-cache-dir -r requirements.txt -t /tmp/deps"
                            " && mkdir -p /asset-output && cp -a /tmp/deps/. /asset-output/"
                            " && cp -r src /asset-output/src"
                        ),
                    ],
                ),
            ),
            memory_size=512,
            timeout=cdk.Duration.seconds(_LAMBDA_TIMEOUT_SEC),
            # Bounds the blast radius of a burst against Bedrock account quota.
            reserved_concurrent_executions=10,
            dead_letter_queue=dead_letter_queue,
            environment_encryption=encryption_key,
            tracing=lambda_.Tracing.ACTIVE,
            log_group=log_group,
            # applicationLogLevelV2 / systemLogLevelV2 require JSON logging_format.
            logging_format=lambda_.LoggingFormat.JSON,
            application_log_level_v2=lambda_.ApplicationLogLevel.INFO,
            system_log_level_v2=lambda_.SystemLogLevel.WARN,
            environment={
                "DEFAULT_PROVIDER": default_provider,
                "BEDROCK_MODEL": bedrock_model,
                "ANTHROPIC_MODEL": "claude-sonnet-4-6",
                "OPENAI_MODEL": "gpt-4o",
                "REQUEST_TIMEOUT": str(_REQUEST_TIMEOUT_SEC),
                "MAX_PARALLEL_CRITERIA": str(_MAX_PARALLEL_CRITERIA),
                # Anthropic / OpenAI API keys are read from this secret at
                # runtime. They are never stored as environment variables.
                "API_KEYS_SECRET_NAME": api_keys_secret.secret_name,
                "POWERTOOLS_SERVICE_NAME": "llm-judge",
                "POWERTOOLS_METRICS_NAMESPACE": "LlmJudge",
                "LOG_LEVEL": "INFO",
            },
            description=(
                "LLM-as-a-Judge: evaluates LLM responses using a multi-criteria "
                "rubric via Anthropic, OpenAI, or Amazon Bedrock."
            ),
        )

        # -----------------------------------------------------------------
        # IAM — Bedrock, scoped to the configured models only
        # -----------------------------------------------------------------

        function.add_to_role_policy(
            iam.PolicyStatement(
                sid="BedrockInvokeConfiguredModels",
                effect=iam.Effect.ALLOW,
                # The Converse API is authorised through bedrock:InvokeModel;
                # bedrock:Converse is granted alongside it to match the action
                # naming used by earlier revisions of this stack. Verify against
                # the IAM Service Authorization Reference before removing it.
                actions=["bedrock:InvokeModel", "bedrock:Converse"],
                resources=self._bedrock_model_resources(
                    allowed_models, profile_regions
                ),
            )
        )

        # -----------------------------------------------------------------
        # IAM — Secrets Manager (this secret only)
        # -----------------------------------------------------------------

        api_keys_secret.grant_read(function)

        # -----------------------------------------------------------------
        # IAM — KMS for the dead-letter queue
        # -----------------------------------------------------------------
        # Lambda writes failed asynchronous invocations to the DLQ using the
        # function's execution role. Because the queue is encrypted with a
        # customer-managed key, that role needs kms:GenerateDataKey in addition
        # to the kms:Decrypt that environment_encryption already grants —
        # otherwise DLQ delivery fails silently and the events are lost.

        encryption_key.grant_encrypt_decrypt(function)

        # -----------------------------------------------------------------
        # IAM — S3 criteria objects (read-only, objects only, no ListBucket)
        # -----------------------------------------------------------------

        function.add_to_role_policy(
            iam.PolicyStatement(
                sid="S3GetCriteriaObject",
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject"],
                resources=[criteria_bucket.arn_for_objects("*")],
            )
        )

        # -----------------------------------------------------------------
        # CloudWatch — alarm topic, alarms, dashboard
        # -----------------------------------------------------------------

        alarm_topic = sns.Topic(
            self,
            "LlmJudgeAlarms",
            topic_name=f"{resource_prefix}-alarms",
            display_name="LLM-as-a-Judge alarms",
            master_key=encryption_key,
            enforce_ssl=True,
        )

        # CloudWatch publishes alarm notifications using its own service
        # principal. Publishing to a topic encrypted with a customer-managed key
        # requires explicit key access; without it alarms transition state but
        # the notification never arrives.
        encryption_key.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowCloudWatchAlarmsToPublishToEncryptedTopic",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("cloudwatch.amazonaws.com")],
                actions=["kms:Decrypt", "kms:GenerateDataKey*"],
                resources=["*"],
            )
        )

        alarms = [
            cloudwatch.Alarm(
                self,
                "FunctionErrorsAlarm",
                alarm_name=f"{resource_prefix}-errors",
                alarm_description="LLM-as-a-Judge Lambda returned an error.",
                metric=function.metric_errors(period=cdk.Duration.minutes(5)),
                threshold=1,
                evaluation_periods=1,
                comparison_operator=(
                    cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
                ),
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            ),
            cloudwatch.Alarm(
                self,
                "FunctionThrottlesAlarm",
                alarm_name=f"{resource_prefix}-throttles",
                alarm_description=(
                    "LLM-as-a-Judge Lambda was throttled — reserved concurrency "
                    "may be too low for current demand."
                ),
                metric=function.metric_throttles(period=cdk.Duration.minutes(5)),
                threshold=1,
                evaluation_periods=1,
                comparison_operator=(
                    cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
                ),
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            ),
            cloudwatch.Alarm(
                self,
                "FunctionDurationAlarm",
                alarm_name=f"{resource_prefix}-duration-p99",
                alarm_description=(
                    "p99 duration exceeded 80% of the configured Lambda timeout."
                ),
                metric=function.metric_duration(
                    period=cdk.Duration.minutes(5), statistic="p99"
                ),
                threshold=_LAMBDA_TIMEOUT_SEC * 1000 * 0.8,
                evaluation_periods=2,
                comparison_operator=(
                    cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
                ),
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            ),
            cloudwatch.Alarm(
                self,
                "DlqDepthAlarm",
                alarm_name=f"{resource_prefix}-dlq-depth",
                alarm_description=(
                    "Messages are sitting in the LLM-as-a-Judge dead-letter queue."
                ),
                metric=dead_letter_queue.metric_approximate_number_of_messages_visible(
                    period=cdk.Duration.minutes(5)
                ),
                threshold=1,
                evaluation_periods=1,
                comparison_operator=(
                    cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
                ),
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            ),
        ]

        for alarm in alarms:
            alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))

        dashboard = cloudwatch.Dashboard(
            self,
            "LlmJudgeDashboard",
            dashboard_name=f"{resource_prefix}",
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Invocations / Errors / Throttles",
                left=[
                    function.metric_invocations(),
                    function.metric_errors(),
                    function.metric_throttles(),
                ],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="Duration (avg / p99)",
                left=[
                    function.metric_duration(statistic="avg"),
                    function.metric_duration(statistic="p99"),
                ],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="Judge outcomes (EMF)",
                left=[
                    cloudwatch.Metric(
                        namespace="LlmJudge",
                        metric_name=name,
                        dimensions_map={"service": "llm-judge"},
                        statistic="Sum",
                    )
                    for name in (
                        "EvaluationsCompleted",
                        "CriterionEvaluationFailed",
                        "BedrockThrottled",
                        "NotAssessableCount",
                    )
                ],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="Dead-letter queue depth",
                left=[
                    dead_letter_queue.metric_approximate_number_of_messages_visible()
                ],
                width=12,
            ),
        )

        # -----------------------------------------------------------------
        # Outputs
        # -----------------------------------------------------------------

        cdk.CfnOutput(
            self,
            "LambdaFunctionArn",
            value=function.function_arn,
            description="ARN of the LLM-as-a-Judge Lambda function.",
            export_name=f"{resource_prefix}-function-arn",
        )

        cdk.CfnOutput(
            self,
            "LambdaFunctionName",
            value=function.function_name,
            description="Name of the LLM-as-a-Judge Lambda function.",
        )

        cdk.CfnOutput(
            self,
            "CriteriaBucketName",
            value=criteria_bucket.bucket_name,
            description="S3 bucket holding evaluation criteria JSON files.",
        )

        cdk.CfnOutput(
            self,
            "ApiKeysSecretName",
            value=api_keys_secret.secret_name,
            description=(
                "Secrets Manager secret holding Anthropic/OpenAI API keys. "
                "Populate with put-secret-value after deployment."
            ),
        )

        cdk.CfnOutput(
            self,
            "DeadLetterQueueUrl",
            value=dead_letter_queue.queue_url,
            description="Dead-letter queue for failed asynchronous invocations.",
        )

        cdk.CfnOutput(
            self,
            "AlarmTopicArn",
            value=alarm_topic.topic_arn,
            description="SNS topic that receives CloudWatch alarm notifications.",
        )

        # -----------------------------------------------------------------
        # cdk-nag suppressions
        # -----------------------------------------------------------------
        # Every suppression below is a deliberate, justified exception. Anything
        # not listed here must be fixed rather than suppressed.

        NagSuppressions.add_resource_suppressions(
            function,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": (
                        "AWSLambdaBasicExecutionRole is the AWS-provided policy "
                        "for CloudWatch Logs access and is the documented way to "
                        "grant it. Every other permission on this role is "
                        "customer-managed and resource-scoped."
                    ),
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": (
                        "Pinned to Python 3.13 rather than the newest runtime "
                        "the CDK knows about. The runtime version is a "
                        "deliberate deployment decision that must be validated "
                        "against the bundled dependency set (anthropic, openai, "
                        "boto3, aws-lambda-powertools) before it moves. Revisit "
                        "this pin when those have been exercised on a newer "
                        "runtime."
                    ),
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": (
                        "Two object-level wildcards remain and both are the "
                        "narrowest form available: s3:GetObject on "
                        "<criteria-bucket>/* (object keys are supplied at "
                        "runtime by the caller) and the X-Ray PutTraceSegments / "
                        "PutTelemetryRecords actions, which AWS defines as "
                        "resource-independent. Bedrock and Secrets Manager "
                        "access name specific ARNs."
                    ),
                },
            ],
            apply_to_children=True,
        )

        NagSuppressions.add_resource_suppressions(
            api_keys_secret,
            [
                {
                    "id": "AwsSolutions-SMG4",
                    "reason": (
                        "The secret holds third-party API keys (Anthropic, "
                        "OpenAI). Secrets Manager cannot rotate credentials it "
                        "does not issue, and neither vendor exposes a rotation "
                        "API to drive from a rotation Lambda. Rotation is a "
                        "manual operational procedure for this secret."
                    ),
                }
            ],
        )

        if stack_manages_bucket:
            NagSuppressions.add_resource_suppressions(
                access_logs_bucket,
                [
                    {
                        "id": "AwsSolutions-S1",
                        "reason": (
                            "This is itself the server access log destination "
                            "for the criteria bucket. Pointing it at itself "
                            "would create a logging loop."
                        ),
                    }
                ],
            )
            # The BucketDeployment construct ships a CDK-managed custom resource
            # whose runtime, role, and policies are not configurable here.
            NagSuppressions.add_resource_suppressions_by_path(
                self,
                (
                    f"/{construct_id}/Custom::CDKBucketDeployment"
                    "8693BB64968944B69AAFB0CC9EB8756C"
                ),
                [
                    {
                        "id": "AwsSolutions-L1",
                        "reason": (
                            "Runtime is chosen by the aws-s3-deployment "
                            "construct and tracks the CDK release, not this "
                            "stack."
                        ),
                    }
                ],
                apply_to_children=True,
            )
            NagSuppressions.add_resource_suppressions_by_path(
                self,
                (
                    f"/{construct_id}/Custom::CDKBucketDeployment"
                    "8693BB64968944B69AAFB0CC9EB8756C/ServiceRole"
                ),
                [
                    {
                        "id": "AwsSolutions-IAM4",
                        "reason": (
                            "Role is generated by the aws-s3-deployment "
                            "construct and is not configurable here."
                        ),
                    },
                    {
                        "id": "AwsSolutions-IAM5",
                        "reason": (
                            "The deployment custom resource needs object-level "
                            "wildcard access to sync criteria files into the "
                            "bucket it owns. Scope is limited to that bucket "
                            "and the CDK asset bucket."
                        ),
                    },
                ],
                apply_to_children=True,
            )

        # Retained as attributes so that Phase-4 constructs and tests can reach
        # them without re-deriving names.
        self.function = function
        self.criteria_bucket = criteria_bucket
        self.encryption_key = encryption_key
        self.dead_letter_queue = dead_letter_queue
        self.alarm_topic = alarm_topic

    # ------------------------------------------------------------------
    # IAM helpers
    # ------------------------------------------------------------------

    def _bedrock_model_resources(
        self,
        model_ids: list[str],
        inference_profile_regions: list[str],
    ) -> list[str]:
        """Build the least-privilege Bedrock resource ARNs for ``model_ids``.

        A model ID whose first dot-separated segment is a known region prefix
        (``jp.anthropic.claude-...``) denotes a cross-region inference profile.
        Invoking it needs the profile ARN in the calling region *and* the
        foundation-model ARN in every region the profile can route to. A plain
        ID (``amazon.nova-lite-v1:0``) needs only the foundation-model ARN in
        the calling region.

        Args:
            model_ids: Bedrock model and/or inference profile IDs to allow.
            inference_profile_regions: Regions that cross-region profiles route
                to. Falls back to the stack region when empty.

        Returns:
            Sorted, de-duplicated list of ARNs for an IAM policy statement.
        """
        regions = inference_profile_regions or [self.region]
        resources: set[str] = set()

        for model_id in model_ids:
            prefix, _, base_model_id = model_id.partition(".")
            if prefix in _INFERENCE_PROFILE_PREFIXES and base_model_id:
                resources.add(
                    f"arn:{self.partition}:bedrock:{self.region}:{self.account}"
                    f":inference-profile/{model_id}"
                )
                for region in regions:
                    resources.add(
                        f"arn:{self.partition}:bedrock:{region}"
                        f"::foundation-model/{base_model_id}"
                    )
            else:
                resources.add(
                    f"arn:{self.partition}:bedrock:{self.region}"
                    f"::foundation-model/{model_id}"
                )

        return sorted(resources)
