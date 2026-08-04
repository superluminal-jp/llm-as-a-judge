#!/usr/bin/env python3
"""CDK application entry point for LLM-as-a-Judge.

Instantiates the :class:`~cdk.stack.LlmJudgeStack` and synthesises the
CloudFormation template. Run via::

    cdk synth
    cdk deploy LlmJudgeStack-dev

Deployment parameters are read from ``config/parameters.json``, optionally
merged with ``config/parameters.local.json`` (same keys override). Command-line
``--context`` / CDK context then take precedence in the stack when non-empty.

The stack is deployed into an **explicit** environment (account + region) rather
than being environment-agnostic: the account comes from ``CDK_DEFAULT_ACCOUNT``
(or the ``AWS_ACCOUNT_ID`` environment variable) and the region from the
``aws_region`` parameter. An explicit environment is what lets the stack build
region-scoped ARNs for the Bedrock IAM policy instead of falling back to
wildcards.

Stack names are suffixed with the ``environment`` parameter (``LlmJudgeStack-dev``,
``LlmJudgeStack-prod``) so that multiple environments can coexist in one account.

See ``config/README.md`` for the parameter file schema.
"""

from __future__ import annotations

import json
import os

import aws_cdk as cdk

from stack import LlmJudgeStack

# Parameter keys whose values are JSON arrays and must not be coerced to str.
_LIST_KEYS = frozenset({"bedrock_allowed_models", "bedrock_inference_profile_regions"})


def _load_parameters() -> dict[str, object]:
    """Load ``config/parameters.json`` and overlay ``parameters.local.json`` if present.

    Scalar values are coerced to ``str`` so that they can be passed straight
    through to CloudFormation. Keys listed in :data:`_LIST_KEYS` keep their
    native list type.

    Returns:
        Merged parameter mapping; later files override earlier keys.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def _read_file(rel: str) -> dict[str, object]:
        path = os.path.join(repo_root, "config", rel)
        if not os.path.isfile(path):
            return {}
        with open(path, encoding="utf-8") as f:
            raw: object = json.load(f)
        if not isinstance(raw, dict):
            return {}
        out: dict[str, object] = {}
        for key, val in raw.items():
            if not isinstance(key, str) or val is None:
                continue
            if key in _LIST_KEYS:
                out[key] = [str(item) for item in val] if isinstance(val, list) else []
            else:
                out[key] = str(val)
        return out

    merged = _read_file("parameters.json")
    merged.update(_read_file("parameters.local.json"))
    return merged


def _param_str(params: dict[str, object], key: str, default: str = "") -> str:
    """Return a scalar parameter as a stripped string, or ``default`` if absent/blank."""
    value = params.get(key)
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _param_list(params: dict[str, object], key: str) -> list[str]:
    """Return a list parameter, filtering out blank entries."""
    value = params.get(key)
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


app = cdk.App()
_params = _load_parameters()


def _context_or_param(key: str, default: str = "") -> str:
    """Resolve a scalar setting from CDK context first, then the parameter files."""
    ctx = app.node.try_get_context(key)
    if ctx is not None and str(ctx).strip():
        return str(ctx).strip()
    return _param_str(_params, key, default)


environment = _context_or_param("environment", "dev")
region = _context_or_param("aws_region", "ap-northeast-1")
account = os.environ.get("CDK_DEFAULT_ACCOUNT") or os.environ.get("AWS_ACCOUNT_ID")

stack = LlmJudgeStack(
    app,
    f"LlmJudgeStack-{environment}",
    env=cdk.Environment(account=account, region=region),
    description="LLM-as-a-Judge evaluation Lambda with multi-provider support.",
    environment_name=environment,
    default_provider=_param_str(_params, "default_provider"),
    bedrock_model=_param_str(_params, "bedrock_model"),
    bedrock_allowed_models=_param_list(_params, "bedrock_allowed_models"),
    bedrock_inference_profile_regions=_param_list(
        _params, "bedrock_inference_profile_regions"
    ),
    criteria_bucket_arn=_param_str(_params, "criteria_bucket_arn"),
)

cdk.Tags.of(app).add("Service", "llm-judge")
cdk.Tags.of(app).add("Environment", environment)

app.synth()
