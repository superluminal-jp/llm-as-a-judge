#!/usr/bin/env python3
"""CDK application entry point for LLM-as-a-Judge.

Instantiates one :class:`~cdk.stack.LlmJudgeStack` per environment. The CFN
stack name is ``LlmJudgeStack-<environment>`` (e.g., ``LlmJudgeStack-dev``,
``LlmJudgeStack-prd``) so dev / prd can coexist in the same AWS account.

Run via::

    cdk synth
    cdk deploy LlmJudgeStack-dev                        # uses parameters.json default
    cdk deploy LlmJudgeStack-prd --context environment=prd

Defaults for ``environment``, ``default_provider``, and ``criteria_bucket_arn``
are read from ``config/parameters.json``, optionally merged with
``config/parameters.local.json`` (same keys override). Command-line
``--context`` then takes precedence in the stack when non-empty.

See ``config/README.md`` for the parameter file schema.
"""

from __future__ import annotations

import json
import os

import aws_cdk as cdk

from stack import LlmJudgeStack


def _load_parameters() -> dict[str, str]:
    """Load ``config/parameters.json`` and overlay ``parameters.local.json`` if present.

    Returns:
        String values only; later files override earlier keys for the same name.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def _read_file(rel: str) -> dict[str, str]:
        path = os.path.join(repo_root, "config", rel)
        if not os.path.isfile(path):
            return {}
        with open(path, encoding="utf-8") as f:
            raw: object = json.load(f)
        if not isinstance(raw, dict):
            return {}
        out: dict[str, str] = {}
        for key, val in raw.items():
            if isinstance(key, str) and val is not None:
                out[key] = str(val)
        return out

    merged = _read_file("parameters.json")
    merged.update(_read_file("parameters.local.json"))
    return merged


app = cdk.App()
_params = _load_parameters()

# Resolve environment label: CDK context > parameters file > "dev".
_env_ctx = app.node.try_get_context("environment")
_environment = (str(_env_ctx).strip() if _env_ctx else "") or _params.get("environment", "dev").strip() or "dev"

LlmJudgeStack(
    app,
    f"LlmJudgeStack-{_environment}",
    description=f"LLM-as-a-Judge evaluation Lambda ({_environment}).",
    environment_label=_environment,
    default_provider=_params.get("default_provider"),
    criteria_bucket_arn=_params.get("criteria_bucket_arn"),
)

app.synth()
