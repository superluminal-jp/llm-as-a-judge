#!/usr/bin/env python3
"""CDK application entry point for LLM-as-a-Judge.

Instantiates the :class:`~cdk.stack.LlmJudgeStack` and synthesises the
CloudFormation template. Run via::

    cdk synth
    cdk deploy LlmJudgeStack

Context keys (set in ``cdk.json`` or via ``--context``):
    default_provider (str):     Default LLM provider (``"anthropic"``,
                                ``"openai"``, or ``"bedrock"``).
    criteria_bucket_arn (str):  ARN of the S3 bucket containing criteria JSON
                                files. Leave empty to skip the S3 IAM policy.
"""

import aws_cdk as cdk

from stack import LlmJudgeStack

app = cdk.App()

LlmJudgeStack(
    app,
    "LlmJudgeStack",
    description="LLM-as-a-Judge evaluation Lambda with multi-provider support.",
)

app.synth()
