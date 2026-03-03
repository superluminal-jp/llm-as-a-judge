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

import os
import shutil
import subprocess
from typing import Any

import aws_cdk as cdk
import aws_cdk.aws_iam as iam
import aws_cdk.aws_lambda as lambda_
import jsii
from constructs import Construct

# ---------------------------------------------------------------------------
# Local bundler (Docker fallback)
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@jsii.implements(cdk.ILocalBundling)
class _LocalBundler:
    """Local bundling fallback used when Docker is unavailable.

    CDK tries the local bundler first; if :meth:`try_bundle` returns ``False``,
    CDK falls back to Docker bundling. This is useful for local ``cdk synth``
    runs on machines where the Docker daemon is not running.
    """

    def try_bundle(self, output_dir: str, options: Any) -> bool:
        """Install runtime dependencies and copy source files locally.

        Args:
            output_dir: The directory CDK expects the bundle to appear in.
            options:    CDK BundlingOptions (unused; accepted for interface
                        compatibility).

        Returns:
            ``True`` on success, ``False`` to signal CDK should use Docker.
        """
        result = subprocess.run(
            ["pip", "install", "-r", "requirements.txt", "-t", output_dir],
            cwd=_REPO_ROOT,
            capture_output=True,
        )
        if result.returncode != 0:
            return False

        # Copy src/ as a package (preserving the directory so that
        # "from src.X import ..." resolves correctly in the Lambda runtime).
        src_dir = os.path.join(_REPO_ROOT, "src")
        dst_src_dir = os.path.join(output_dir, "src")
        shutil.copytree(src_dir, dst_src_dir, dirs_exist_ok=True)
        return True


class LlmJudgeStack(cdk.Stack):
    """CloudFormation stack for the LLM-as-a-Judge Lambda function.

    All configuration is driven by CDK context values (``cdk.json`` or
    ``--context`` flags) so that the same stack definition can be reused
    across environments (dev, staging, prod).

    Context keys:
        default_provider (str):     LLM provider used when the Lambda event
                                    does not specify one. Defaults to
                                    ``"bedrock"``.
        criteria_bucket_arn (str):  ARN of the S3 bucket that stores criteria
                                    JSON files. When provided, an
                                    ``s3:GetObject`` policy is attached to the
                                    Lambda execution role.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        """Initialise the LlmJudgeStack.

        Args:
            scope:        CDK construct scope (the :class:`~aws_cdk.App`).
            construct_id: Logical ID used to identify this stack in
                          CloudFormation and CDK.
            **kwargs:     Additional keyword arguments forwarded to
                          :class:`~aws_cdk.Stack`.
        """
        super().__init__(scope, construct_id, **kwargs)

        # Read CDK context values; fall back to safe defaults.
        default_provider: str = self.node.try_get_context("default_provider") or "bedrock"
        criteria_bucket_arn: str = self.node.try_get_context("criteria_bucket_arn") or ""

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
            # Bundle src/ as a package alongside pip-installed dependencies.
            # _LocalBundler runs first (no Docker required); CDK falls back to
            # Docker only when the local bundler returns False.
            code=lambda_.Code.from_asset(
                "..",
                bundling=cdk.BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    local=_LocalBundler(),
                    command=[
                        "bash",
                        "-c",
                        (
                            "pip install -r requirements.txt -t /asset-output"
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
