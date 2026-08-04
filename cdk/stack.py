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
import aws_cdk.aws_stepfunctions as sfn
import aws_cdk.aws_stepfunctions_tasks as tasks
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
# Also used as the Map state's MaxConcurrency in the Step Functions workflow.
_MAX_PARALLEL_CRITERIA = 5

# Per-function reserved concurrency. Bounds how many invocations can run at once
# and therefore how hard the service can push against Bedrock account quota.
_RESERVED_CONCURRENCY = 10

# How long staged job payloads survive in the jobs bucket. Long enough to debug
# a failed execution, short enough that submitted material is not retained.
_JOB_RETENTION_DAYS = 7

# Express workflows are capped at 5 minutes; this keeps the state machine's own
# timeout just inside that so a hung execution fails as a timeout rather than
# being cut off by the service limit.
_STATE_MACHINE_TIMEOUT_SEC = 290

# Per-criterion retry policy, applied to the Map state. Backoff happens between
# Lambda invocations, so a throttled criterion costs no billed execution time.
_RETRYABLE_ERRORS = [
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceQuotaExceededException",
    "ModelTimeoutException",
    "Lambda.TooManyRequestsException",
    "Lambda.ServiceException",
    "Lambda.SdkClientException",
]


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
        # S3 — jobs bucket (claim-check payload staging)
        # -----------------------------------------------------------------
        # Step Functions caps inter-state data at 256 KB, so the prepare step
        # writes the full evaluation payload here and only an s3:// URI travels
        # through the workflow. Objects are transient; the lifecycle rule is the
        # only thing that deletes them, which leaves a failed execution's
        # payload available for debugging in the meantime.

        jobs_bucket = s3.Bucket(
            self,
            "JobsBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ExpireStagedJobs",
                    expiration=cdk.Duration.days(_JOB_RETENTION_DAYS),
                    abort_incomplete_multipart_upload_after=cdk.Duration.days(1),
                )
            ],
            server_access_logs_bucket=(
                access_logs_bucket if stack_manages_bucket else None
            ),
            server_access_logs_prefix=(
                "jobs-bucket/" if stack_manages_bucket else None
            ),
            removal_policy=(
                cdk.RemovalPolicy.RETAIN if is_production else cdk.RemovalPolicy.DESTROY
            ),
            auto_delete_objects=not is_production,
        )

        # -----------------------------------------------------------------
        # Lambda functions
        # -----------------------------------------------------------------
        # Four entry points share one asset. Splitting them gives each step of
        # the workflow its own execution role, so the criterion worker — the
        # only one that talks to Bedrock — cannot write to the jobs bucket, and
        # the prepare step cannot invoke a model.

        shared_code = lambda_.Code.from_asset(
            ".",
            # `exclude` keeps unrelated files out of the asset hash so that
            # editing docs or tests does not trigger a Lambda redeploy.
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
            # Bundle src/ as a package alongside pip-installed dependencies
            # (requires Docker for cdk synth / deploy).
            # Path is relative to cdk.json (repo root), not the cdk/ package dir.
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
        )

        shared_environment = {
            "DEFAULT_PROVIDER": default_provider,
            "BEDROCK_MODEL": bedrock_model,
            "ANTHROPIC_MODEL": "claude-sonnet-4-6",
            "OPENAI_MODEL": "gpt-4o",
            "REQUEST_TIMEOUT": str(_REQUEST_TIMEOUT_SEC),
            "MAX_PARALLEL_CRITERIA": str(_MAX_PARALLEL_CRITERIA),
            "JOBS_BUCKET": jobs_bucket.bucket_name,
            # Anthropic / OpenAI API keys are read from this secret at
            # runtime. They are never stored as environment variables.
            "API_KEYS_SECRET_NAME": api_keys_secret.secret_name,
            "POWERTOOLS_SERVICE_NAME": "llm-judge",
            "POWERTOOLS_METRICS_NAMESPACE": "LlmJudge",
            "LOG_LEVEL": "INFO",
        }

        def _make_function(
            construct_key: str,
            name_suffix: str,
            handler_path: str,
            description: str,
            *,
            timeout_sec: int,
            memory_mb: int = 512,
            with_dlq: bool = False,
        ) -> lambda_.Function:
            """Create one of the service's Lambda functions from the shared asset."""
            function_log_group = logs.LogGroup(
                self,
                f"{construct_key}LogGroup",
                log_group_name=f"/aws/lambda/{resource_prefix}{name_suffix}",
                retention=(
                    logs.RetentionDays.THREE_MONTHS
                    if is_production
                    else logs.RetentionDays.ONE_MONTH
                ),
                removal_policy=(
                    cdk.RemovalPolicy.RETAIN
                    if is_production
                    else cdk.RemovalPolicy.DESTROY
                ),
            )
            return lambda_.Function(
                self,
                construct_key,
                function_name=f"{resource_prefix}{name_suffix}",
                runtime=lambda_.Runtime.PYTHON_3_13,
                # ARM64/Graviton: cheaper per GB-second and equally suited to
                # this I/O-bound workload, which spends its time waiting on
                # model APIs.
                architecture=lambda_.Architecture.ARM_64,
                handler=handler_path,
                code=shared_code,
                memory_size=memory_mb,
                timeout=cdk.Duration.seconds(timeout_sec),
                # Bounds the blast radius of a burst against Bedrock quota.
                reserved_concurrent_executions=_RESERVED_CONCURRENCY,
                dead_letter_queue=dead_letter_queue if with_dlq else None,
                environment_encryption=encryption_key,
                tracing=lambda_.Tracing.ACTIVE,
                log_group=function_log_group,
                # applicationLogLevelV2 / systemLogLevelV2 require JSON format.
                logging_format=lambda_.LoggingFormat.JSON,
                application_log_level_v2=lambda_.ApplicationLogLevel.INFO,
                system_log_level_v2=lambda_.SystemLogLevel.WARN,
                environment=dict(shared_environment),
                description=description,
            )

        # Direct-invoke entry point. Retained as a fully functional path, not a
        # deprecated shim: it evaluates every criterion in one invocation, which
        # stays the simplest option for small criteria sets and keeps the
        # existing `aws lambda invoke` contract working unchanged.
        function = _make_function(
            "LlmJudgeFunction",
            "",
            "src.handler.lambda_handler",
            (
                "LLM-as-a-Judge: evaluates LLM responses using a multi-criteria "
                "rubric via Anthropic, OpenAI, or Amazon Bedrock (single-Lambda "
                "path)."
            ),
            timeout_sec=_LAMBDA_TIMEOUT_SEC,
            with_dlq=True,
        )

        prepare_function = _make_function(
            "PrepareFunction",
            "-prepare",
            "src.handlers.prepare.handler",
            "LLM-as-a-Judge workflow: validate the request and stage it in S3.",
            timeout_sec=60,
            memory_mb=256,
        )

        evaluate_criterion_function = _make_function(
            "EvaluateCriterionFunction",
            "-evaluate-criterion",
            "src.handlers.evaluate_criterion.handler",
            "LLM-as-a-Judge workflow: score exactly one criterion.",
            timeout_sec=_LAMBDA_TIMEOUT_SEC,
        )

        summarize_function = _make_function(
            "SummarizeFunction",
            "-summarize",
            "src.handlers.summarize.handler",
            "LLM-as-a-Judge workflow: synthesise the summary and final response.",
            timeout_sec=_LAMBDA_TIMEOUT_SEC,
        )

        # -----------------------------------------------------------------
        # IAM — per-function, least privilege
        # -----------------------------------------------------------------

        bedrock_statement = iam.PolicyStatement(
            sid="BedrockInvokeConfiguredModels",
            effect=iam.Effect.ALLOW,
            # The Converse API is authorised through bedrock:InvokeModel;
            # bedrock:Converse is granted alongside it to match the action
            # naming used by earlier revisions of this stack. Verify against
            # the IAM Service Authorization Reference before removing it.
            actions=["bedrock:InvokeModel", "bedrock:Converse"],
            resources=self._bedrock_model_resources(allowed_models, profile_regions),
        )

        criteria_read_statement = iam.PolicyStatement(
            sid="S3GetCriteriaObject",
            effect=iam.Effect.ALLOW,
            actions=["s3:GetObject"],
            resources=[criteria_bucket.arn_for_objects("*")],
        )

        # Only the functions that actually call a model get Bedrock access.
        # PrepareFunction never invokes one.
        for model_caller in (
            function,
            evaluate_criterion_function,
            summarize_function,
        ):
            model_caller.add_to_role_policy(bedrock_statement)
            api_keys_secret.grant_read(model_caller)

        # Only the functions that resolve a criteria file read the criteria
        # bucket. The workflow resolves criteria once, in PrepareFunction.
        for criteria_reader in (function, prepare_function):
            criteria_reader.add_to_role_policy(criteria_read_statement)

        # Jobs bucket: prepare writes, the other two only read.
        jobs_bucket.grant_put(prepare_function)
        jobs_bucket.grant_read(evaluate_criterion_function)
        jobs_bucket.grant_read(summarize_function)

        # -----------------------------------------------------------------
        # IAM — KMS for the dead-letter queue
        # -----------------------------------------------------------------
        # Lambda writes failed asynchronous invocations to the DLQ using the
        # function's execution role. Because the queue is encrypted with a
        # customer-managed key, that role needs kms:GenerateDataKey in addition
        # to the kms:Decrypt that environment_encryption already grants —
        # otherwise DLQ delivery fails silently and the events are lost.

        encryption_key.grant_encrypt_decrypt(function)

        # The workflow functions only need to decrypt their own environment.
        for workflow_function in (
            prepare_function,
            evaluate_criterion_function,
            summarize_function,
        ):
            encryption_key.grant_decrypt(workflow_function)

        # -----------------------------------------------------------------
        # Step Functions — Express workflow
        # -----------------------------------------------------------------

        state_machine = self._build_state_machine(
            resource_prefix=resource_prefix,
            is_production=is_production,
            prepare_function=prepare_function,
            evaluate_criterion_function=evaluate_criterion_function,
            summarize_function=summarize_function,
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
            cloudwatch.Alarm(
                self,
                "WorkflowFailuresAlarm",
                alarm_name=f"{resource_prefix}-workflow-failures",
                alarm_description=(
                    "A LLM-as-a-Judge Step Functions execution failed. Check the "
                    "execution history for the criterion that could not be scored."
                ),
                metric=state_machine.metric_failed(period=cdk.Duration.minutes(5)),
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
            cloudwatch.GraphWidget(
                title="Workflow executions",
                left=[
                    state_machine.metric_started(),
                    state_machine.metric_succeeded(),
                    state_machine.metric_failed(),
                    state_machine.metric_throttled(),
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

        cdk.CfnOutput(
            self,
            "StateMachineArn",
            value=state_machine.state_machine_arn,
            description=(
                "Express state machine for the fan-out evaluation workflow. "
                "Invoke with: aws stepfunctions start-sync-execution."
            ),
            export_name=f"{resource_prefix}-workflow-arn",
        )

        cdk.CfnOutput(
            self,
            "JobsBucketName",
            value=jobs_bucket.bucket_name,
            description=(
                "Bucket staging evaluation payloads for the workflow. Objects "
                f"expire after {_JOB_RETENTION_DAYS} days."
            ),
        )

        # -----------------------------------------------------------------
        # cdk-nag suppressions
        # -----------------------------------------------------------------
        # Every suppression below is a deliberate, justified exception. Anything
        # not listed here must be fixed rather than suppressed.

        for lambda_construct in (
            function,
            prepare_function,
            evaluate_criterion_function,
            summarize_function,
        ):
            NagSuppressions.add_resource_suppressions(
                lambda_construct,
                [
                    {
                        "id": "AwsSolutions-IAM4",
                        "reason": (
                            "AWSLambdaBasicExecutionRole is the AWS-provided "
                            "policy for CloudWatch Logs access and is the "
                            "documented way to grant it. Every other permission "
                            "on this role is customer-managed and "
                            "resource-scoped."
                        ),
                    },
                    {
                        "id": "AwsSolutions-L1",
                        "reason": (
                            "Pinned to Python 3.13 rather than the newest "
                            "runtime the CDK knows about. The runtime version "
                            "is a deliberate deployment decision that must be "
                            "validated against the bundled dependency set "
                            "(anthropic, openai, boto3, aws-lambda-powertools) "
                            "before it moves. Revisit this pin when those have "
                            "been exercised on a newer runtime."
                        ),
                    },
                    {
                        "id": "AwsSolutions-IAM5",
                        "reason": (
                            "The remaining wildcards are object-level and are "
                            "the narrowest form available: s3:GetObject on "
                            "<bucket>/* (object keys are supplied at runtime by "
                            "the caller) and the X-Ray PutTraceSegments / "
                            "PutTelemetryRecords actions, which AWS defines as "
                            "resource-independent. Bedrock and Secrets Manager "
                            "access name specific ARNs."
                        ),
                    },
                ],
                apply_to_children=True,
            )

        NagSuppressions.add_resource_suppressions(
            state_machine,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": (
                        "The execution role's wildcards are generated by the CDK "
                        "and have no narrower form: lambda:InvokeFunction is "
                        "granted on <function-arn>:* to cover published "
                        "versions and aliases of the three named workflow "
                        "functions, and the X-Ray and CloudWatch Logs delivery "
                        "actions required for tracing and vended logs are "
                        "defined by AWS as resource-independent."
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
    # Step Functions
    # ------------------------------------------------------------------

    def _build_state_machine(
        self,
        *,
        resource_prefix: str,
        is_production: bool,
        prepare_function: lambda_.IFunction,
        evaluate_criterion_function: lambda_.IFunction,
        summarize_function: lambda_.IFunction,
    ) -> sfn.StateMachine:
        """Build the Express workflow that fans criteria out across Lambdas.

        Shape::

            Prepare -> Map(MaxConcurrency)[EvaluateCriterion] -> Summarize

        Express (rather than Standard) keeps the request/response contract: the
        caller uses ``StartSyncExecution`` and gets the evaluation back, matching
        how the direct-invoke Lambda behaves today. The 5-minute Express ceiling
        is the binding constraint on how many criteria one execution can carry.

        Args:
            resource_prefix: Name prefix shared by this stack's resources.
            is_production:   Selects log retention and removal policy.
            prepare_function: Validates and stages the request.
            evaluate_criterion_function: Scores one criterion.
            summarize_function: Aggregates results into the final response.

        Returns:
            The configured :class:`~aws_cdk.aws_stepfunctions.StateMachine`.
        """
        prepare = tasks.LambdaInvoke(
            self,
            "Prepare",
            lambda_function=prepare_function,
            # Unwrap the Lambda envelope so downstream states see the handler's
            # return value directly.
            payload_response_only=True,
        )

        evaluate_criterion = tasks.LambdaInvoke(
            self,
            "EvaluateCriterion",
            lambda_function=evaluate_criterion_function,
            payload_response_only=True,
        )

        evaluate_map = sfn.Map(
            self,
            "EvaluateCriteria",
            items_path=sfn.JsonPath.string_at("$.items"),
            # Hard cap on concurrent Bedrock calls, declared in the workflow
            # rather than left to whatever the caller passes at runtime.
            max_concurrency=_MAX_PARALLEL_CRITERIA,
            result_path="$.results",
        )
        evaluate_map.item_processor(evaluate_criterion)

        # Retry the whole Map branch rather than individual criteria inside the
        # Lambda: backoff then runs between invocations, on the service's clock
        # instead of billed execution time. FULL jitter spreads retries so that
        # a throttled batch does not resynchronise and throttle again.
        evaluate_map.add_retry(
            errors=_RETRYABLE_ERRORS,
            interval=cdk.Duration.seconds(2),
            max_attempts=4,
            backoff_rate=2,
            jitter_strategy=sfn.JitterType.FULL,
        )

        summarize = tasks.LambdaInvoke(
            self,
            "Summarize",
            lambda_function=summarize_function,
            payload=sfn.TaskInput.from_object(
                {
                    "job_uri": sfn.JsonPath.string_at("$.job_uri"),
                    "results": sfn.JsonPath.object_at("$.results"),
                }
            ),
            payload_response_only=True,
        )
        summarize.add_retry(
            errors=_RETRYABLE_ERRORS,
            interval=cdk.Duration.seconds(2),
            max_attempts=4,
            backoff_rate=2,
            jitter_strategy=sfn.JitterType.FULL,
        )

        workflow_log_group = logs.LogGroup(
            self,
            "WorkflowLogGroup",
            log_group_name=f"/aws/vendedlogs/states/{resource_prefix}",
            retention=(
                logs.RetentionDays.THREE_MONTHS
                if is_production
                else logs.RetentionDays.ONE_MONTH
            ),
            removal_policy=(
                cdk.RemovalPolicy.RETAIN if is_production else cdk.RemovalPolicy.DESTROY
            ),
        )

        return sfn.StateMachine(
            self,
            "EvaluationWorkflow",
            state_machine_name=f"{resource_prefix}-workflow",
            state_machine_type=sfn.StateMachineType.EXPRESS,
            definition_body=sfn.DefinitionBody.from_chainable(
                prepare.next(evaluate_map.next(summarize))
            ),
            timeout=cdk.Duration.seconds(_STATE_MACHINE_TIMEOUT_SEC),
            tracing_enabled=True,
            logs=sfn.LogOptions(
                destination=workflow_log_group,
                level=sfn.LogLevel.ALL,
                # The state carries the judge's per-criterion reasoning, which
                # quotes the submitted material. Logging execution data would
                # copy that into CloudWatch Logs; the state machine's structure
                # is observable without it.
                include_execution_data=False,
            ),
            removal_policy=(
                cdk.RemovalPolicy.RETAIN if is_production else cdk.RemovalPolicy.DESTROY
            ),
        )

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
