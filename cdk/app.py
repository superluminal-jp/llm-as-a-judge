#!/usr/bin/env python3
"""CDK application entry point for LLM-as-a-Judge.

Instantiates the :class:`~cdk.stack.LlmJudgeStack` and synthesises the
CloudFormation template. Run via::

    cdk synth
    cdk deploy LlmJudgeStack

Defaults for ``default_provider`` and ``criteria_bucket_arn`` are read from
``config/parameters.json``, optionally merged with ``config/parameters.local.json``
(same keys override). Command-line ``--context`` / CDK context then take
precedence in the stack when non-empty.

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

LlmJudgeStack(
    app,
    "LlmJudgeStack",
    description="LLM-as-a-Judge evaluation Lambda with multi-provider support.",
    default_provider=_params.get("default_provider"),
    criteria_bucket_arn=_params.get("criteria_bucket_arn"),
)

app.synth()
