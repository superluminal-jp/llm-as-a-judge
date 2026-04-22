"""CDK stack definition for LLM-as-a-Judge Lambda deployment.

Deploys a single Lambda function with:
- Python 3.12 runtime (``aws_lambda.Runtime.PYTHON_3_12``)
- 512 MB memory, 60-second timeout
- IAM: ``bedrock:InvokeModel`` on all foundation models
- IAM: ``s3:GetObject`` on the criteria bucket (when ``criteria_bucket_arn``
  CDK context is set)
- Environment variables sourced from CDK context / CloudFormation parameters
- CfnOutput: Lambda function ARN

API key management:
    Anthropic and OpenAI API keys are passed as Lambda environment variables.
    For production use, store them in AWS Secrets Manager and reference them
    here via ``secretsmanager.Secret.from_secret_name_v2``.
"""

from __future__ import annotations

import aws_cdk as cdk
import aws_cdk.aws_iam as iam
import aws_cdk.aws_lambda as lambda_
from constructs import Construct


class LlmJudgeStack(cdk.Stack):
    """CloudFormation stack for the LLM-as-a-Judge Lambda function.

    All configuration is driven by CDK context values (``cdk.json`` or
    ``--context`` flags) so that the same stack definition can be reused
    across environments (dev, staging, prod).

    Context keys (``--context`` / ``cdk.json``) override ``config/parameters.json``
    when set to a non-empty value:

        default_provider (str):     LLM provider used when the Lambda event
                                    does not specify one. Defaults to
                                    ``"bedrock"``.
        criteria_bucket_arn (str):  ARN of the S3 bucket that stores criteria
                                    JSON files. When provided, an
                                    ``s3:GetObject`` policy is attached to the
                                    Lambda execution role.

    Keyword arguments (from :mod:`cdk.app` reading ``config/parameters.json``) fill
    values when context is unset or empty.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        default_provider: str | None = None,
        criteria_bucket_arn: str | None = None,
        **kwargs,
    ) -> None:
        """Initialise the LlmJudgeStack.

        Args:
            scope:        CDK construct scope (the :class:`~aws_cdk.App`).
            construct_id: Logical ID used to identify this stack in
                          CloudFormation and CDK.
            default_provider: Optional override from ``config/parameters.json``.
            criteria_bucket_arn: Optional override from ``config/parameters.json``.
            **kwargs:     Additional keyword arguments forwarded to
                          :class:`~aws_cdk.Stack`.
        """
        super().__init__(scope, construct_id, **kwargs)

        def _first_non_empty(*vals: object) -> str | None:
            for v in vals:
                if v is None:
                    continue
                s = str(v).strip()
                if s:
                    return s
            return None

        default_provider = (
            _first_non_empty(
                self.node.try_get_context("default_provider"),
                default_provider,
            )
            or "bedrock"
        )
        criteria_bucket_arn = _first_non_empty(
            self.node.try_get_context("criteria_bucket_arn"),
            criteria_bucket_arn,
        ) or ""

        # -----------------------------------------------------------------
        # Lambda function
        # -----------------------------------------------------------------

        function = lambda_.Function(
            self,
            "LlmJudgeFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            # Handler path: src.handler module → lambda_handler function.
            # The src/ package is preserved in the bundle so that intra-package
            # imports (from src.config, from src.criteria, …) resolve correctly.
            handler="src.handler.lambda_handler",
            # Bundle src/ as a package alongside pip-installed dependencies
            # (requires Docker for cdk synth / deploy).
            # Path is relative to cdk.json (repo root), not the cdk/ package dir.
            code=lambda_.Code.from_asset(
                ".",
                bundling=cdk.BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
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
            timeout=cdk.Duration.seconds(60),
            environment={
                "DEFAULT_PROVIDER": default_provider,
                "POWERTOOLS_SERVICE_NAME": "llm-judge",
                "LOG_LEVEL": "INFO",
                # API keys: set these via Lambda console, Secrets Manager
                # integration, or a separate environment-specific config.
                # Do NOT hard-code keys here.
                "ANTHROPIC_MODEL": "claude-sonnet-4-6",
                "OPENAI_MODEL": "gpt-4o",
                # Claude Sonnet 4.6 on Bedrock (anthropic.claude-sonnet-4-6).
                "BEDROCK_MODEL": "anthropic.claude-sonnet-4-6",
                "REQUEST_TIMEOUT": "30",
            },
            description=(
                "LLM-as-a-Judge: evaluates LLM responses using a multi-criteria "
                "rubric via Anthropic, OpenAI, or Amazon Bedrock."
            ),
        )

        # -----------------------------------------------------------------
        # IAM — Bedrock: allow invoking any foundation model
        # -----------------------------------------------------------------

        function.add_to_role_policy(
            iam.PolicyStatement(
                sid="BedrockInvokeModel",
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel"],
                resources=["arn:aws:bedrock:*::foundation-model/*"],
            )
        )

        # -----------------------------------------------------------------
        # IAM — Bedrock Converse API (separate action)
        # -----------------------------------------------------------------

        function.add_to_role_policy(
            iam.PolicyStatement(
                sid="BedrockConverse",
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel", "bedrock:Converse"],
                resources=["arn:aws:bedrock:*::foundation-model/*"],
            )
        )

        # -----------------------------------------------------------------
        # IAM — S3: allow reading criteria files (conditional)
        # -----------------------------------------------------------------

        if criteria_bucket_arn:
            function.add_to_role_policy(
                iam.PolicyStatement(
                    sid="S3GetCriteriaObject",
                    effect=iam.Effect.ALLOW,
                    actions=["s3:GetObject"],
                    resources=[f"{criteria_bucket_arn}/*"],
                )
            )

        # -----------------------------------------------------------------
        # Outputs
        # -----------------------------------------------------------------

        cdk.CfnOutput(
            self,
            "LambdaFunctionArn",
            value=function.function_arn,
            description="ARN of the LLM-as-a-Judge Lambda function.",
            export_name="LlmJudgeFunctionArn",
        )

        cdk.CfnOutput(
            self,
            "LambdaFunctionName",
            value=function.function_name,
            description="Name of the LLM-as-a-Judge Lambda function.",
        )
