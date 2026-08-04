#!/usr/bin/env python3
"""Run multiple invocation patterns against a deployed LlmJudgeStack.

Exercises both workflows with the same cases. The synchronous (Express) and
asynchronous (Standard) state machines share one definition, so running
``TARGET=async`` after ``TARGET=sync`` is the end-to-end check that they stay in
step and that the response is identical whichever way it was produced.

Uses Bedrock with ``amazon.nova-lite-v1:0`` in each payload (on-demand model).

Environment:
    AWS_REGION            Override region (default: config/parameters.json ``aws_region``).
    ENVIRONMENT           Environment suffix used to build the stack name
                          (default: config/parameters.json ``environment``).
    STACK_NAME            Skip the ``LlmJudgeStack-<environment>`` convention.
    TARGET                ``sync`` (default) or ``async``.
    STATE_MACHINE_ARN     Skip the CloudFormation output lookup.
    ASYNC_POLL_TIMEOUT    Seconds to wait for an async execution (default 600).

Usage (from repo root)::

    python3 scripts/workflow_pattern_tests.py
    TARGET=async python3 scripts/workflow_pattern_tests.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
NOVA = "amazon.nova-lite-v1:0"


def _load_parameters() -> dict[str, Any]:
    path = REPO_ROOT / "config" / "parameters.json"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    return raw if isinstance(raw, dict) else {}


def _bucket_from_arn(arn: str) -> str | None:
    m = re.match(r"^arn:aws:s3:::([^/]+)$", arn.strip())
    return m.group(1) if m else None


def _stack_outputs(region: str, environment: str) -> dict[str, str]:
    """Return the deployed stack's outputs keyed by OutputKey."""
    import boto3

    cf = boto3.client("cloudformation", region_name=region)
    stack_name = os.environ.get("STACK_NAME", f"LlmJudgeStack-{environment}")
    stacks = cf.describe_stacks(StackName=stack_name)
    outputs = stacks["Stacks"][0].get("Outputs") or []
    return {str(o["OutputKey"]): str(o["OutputValue"]) for o in outputs}


def _failure(raw: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Normalise a failed execution into the ``(body, error)`` shape used below."""
    error = str(raw.get("error", "ExecutionFailed"))
    return (
        {"errorType": error, "errorMessage": str(raw.get("cause", ""))[:2000]},
        error,
    )


def _invoke_sync(
    client: Any,
    state_machine_arn: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    """Run the Express workflow and return its output directly."""
    raw = client.start_sync_execution(
        stateMachineArn=state_machine_arn,
        input=json.dumps(payload, ensure_ascii=False),
    )
    if raw.get("status") != "SUCCEEDED":
        return _failure(raw)
    return json.loads(raw["output"]), None


def _invoke_async(
    client: Any,
    state_machine_arn: str,
    payload: dict[str, Any],
    poll_timeout: int,
) -> tuple[dict[str, Any], str | None]:
    """Start the Standard workflow and poll until it settles.

    Polling exists only so that this script can assert on a result; real callers
    of the asynchronous workflow collect it from the jobs bucket instead.
    """
    started = client.start_execution(
        stateMachineArn=state_machine_arn,
        input=json.dumps(payload, ensure_ascii=False),
    )
    execution_arn = started["executionArn"]

    deadline = time.monotonic() + poll_timeout
    while True:
        described = client.describe_execution(executionArn=execution_arn)
        status = described["status"]
        if status != "RUNNING":
            break
        if time.monotonic() > deadline:
            return (
                {
                    "errorType": "PollTimeout",
                    "errorMessage": (
                        f"execution still RUNNING after {poll_timeout}s: "
                        f"{execution_arn}"
                    ),
                },
                "PollTimeout",
            )
        time.sleep(2)

    if status != "SUCCEEDED":
        return _failure(described)
    return json.loads(described["output"]), None


def main() -> int:
    params = _load_parameters()
    region = os.environ.get("AWS_REGION", params.get("aws_region", "ap-northeast-1"))
    environment = os.environ.get(
        "ENVIRONMENT", str(params.get("environment", "dev") or "dev")
    )
    target = os.environ.get("TARGET", "sync").strip().lower()
    if target not in ("sync", "async"):
        print(f"TARGET must be 'sync' or 'async', got {target!r}", file=sys.stderr)
        return 2

    import boto3

    outputs = _stack_outputs(region, environment)

    # The criteria bucket is now created by the stack, so prefer its output over
    # config/parameters.json (which no longer carries a real ARN).
    bucket = outputs.get("CriteriaBucketName") or _bucket_from_arn(
        str(params.get("criteria_bucket_arn", "") or "")
    )

    output_key = "SyncStateMachineArn" if target == "sync" else "AsyncStateMachineArn"
    state_machine_arn = os.environ.get("STATE_MACHINE_ARN") or outputs.get(
        output_key, ""
    )
    if not state_machine_arn:
        print(f"{output_key} output missing on the stack", file=sys.stderr)
        return 2

    sfn_client = boto3.client("stepfunctions", region_name=region)
    target_label = state_machine_arn.rsplit(":", 1)[-1]
    poll_timeout = int(os.environ.get("ASYNC_POLL_TIMEOUT", "600"))

    if target == "sync":

        def run(payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
            return _invoke_sync(sfn_client, state_machine_arn, payload)
    else:

        def run(payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
            return _invoke_async(
                sfn_client, state_machine_arn, payload, poll_timeout
            )

    base_paired = {
        "prompt": "要約してください: 水はH2Oです。",
        "response": "水の化学式はH2Oです。",
        "provider": "bedrock",
        "judge_model": NOVA,
    }

    cases: list[tuple[str, dict[str, Any], bool, str]] = []

    # (id, payload, expect_success, notes)
    cases.append(
        (
            "paired_balanced_builtin",
            dict(base_paired),
            True,
            "組み込み Balanced 4 軸（criteria_file なし）",
        )
    )

    if bucket:
        prefix = f"s3://{bucket}/criteria"
        cases.append(
            (
                "paired_s3_default_7axis",
                {**base_paired, "criteria_file": f"{prefix}/default.json"},
                True,
                "S3 default.json（7 軸）",
            )
        )
        cases.append(
            (
                "paired_s3_disclosure",
                {
                    **base_paired,
                    "prompt": "不開示決定の法的評価を求めます。",
                    "response": "第5条第1号に該当し不開示とします。",
                    "criteria_file": f"{prefix}/disclosure.json",
                },
                True,
                "S3 disclosure クライテリア",
            )
        )

    cases.append(
        (
            "prompt_only",
            {
                "prompt": "次の指示に従ってコードを書いてください。",
                "response": "",
                "provider": "bedrock",
                "judge_model": NOVA,
            },
            True,
            "プロンプトのみ（応答空）",
        )
    )
    cases.append(
        (
            "response_only",
            {
                "prompt": "",
                "response": "結論: リスクは低いと判断します。",
                "provider": "bedrock",
                "judge_model": NOVA,
            },
            True,
            "応答のみ（プロンプト空）",
        )
    )
    cases.append(
        (
            "response_only_omit_prompt_key",
            {
                "response": "省略されたプロンプトに対する回答です。",
                "provider": "bedrock",
                "judge_model": NOVA,
            },
            True,
            "prompt キー省略・応答のみ",
        )
    )
    cases.append(
        (
            "paired_descriptors",
            {
                **base_paired,
                "prompt_descriptor": "社内ポリシー草案",
                "response_descriptor": "社内チャットボット出力",
            },
            True,
            "prompt_descriptor / response_descriptor",
        )
    )
    cases.append(
        (
            "paired_system_prompt_and_contexts",
            {
                **base_paired,
                "system_prompt": "あなたは慎重な監査担当です。",
                "contexts": [
                    "[1] 参照: 開示は原則とする。",
                    "[2] 例外事由を個別に検討すること。",
                ],
            },
            True,
            "system_prompt + contexts（リスト）",
        )
    )
    cases.append(
        (
            "contexts_single_string",
            {
                **base_paired,
                "contexts": "単一文字列の追加コンテキスト。",
            },
            True,
            "contexts を文字列で渡す",
        )
    )

    cases.append(
        (
            "validation_both_empty",
            {"prompt": "", "response": "", "provider": "bedrock"},
            False,
            "両方空 → ValidationError",
        )
    )
    cases.append(
        (
            "validation_whitespace_only",
            {"prompt": "  \t", "response": "\n", "provider": "bedrock"},
            False,
            "両方空白のみ → ValidationError",
        )
    )
    cases.append(
        (
            "validation_descriptor_control_char",
            {
                **base_paired,
                "prompt_descriptor": "bad\x00",
            },
            False,
            "descriptor に NUL → ValidationError",
        )
    )
    cases.append(
        (
            "validation_prompt_not_string",
            {"prompt": 123, "response": "ok", "provider": "bedrock"},
            False,
            "prompt が数値 → ValidationError",
        )
    )

    passed = 0
    failed = 0
    print(f"Region={region} Target={target} ({target_label})\n")

    for case_id, payload, expect_ok, note in cases:
        body, fn_err = run(payload)
        ok = fn_err is None and "errorMessage" not in body
        if expect_ok:
            success = ok
            if success:
                ca = body.get("criterion_assessability") or {}
                cs = body.get("criterion_scores") or {}
                detail = f"assessability={len(ca)} scores={len(cs)}"
            else:
                detail = body.get("errorMessage", str(body))[:200]
        else:
            success = not ok and (
                "ValidationError" in str(body.get("errorType", ""))
                or "At least one" in str(body.get("errorMessage", ""))
                or "must be a string" in str(body.get("errorMessage", ""))
                or "control character" in str(body.get("errorMessage", ""))
            )
            detail = (
                body.get("errorType", "")
                + ": "
                + str(body.get("errorMessage", ""))[:120]
            )

        mark = "PASS" if success else "FAIL"
        if success:
            passed += 1
        else:
            failed += 1
        print(f"[{mark}] {case_id}")
        print(f"       {note}")
        print(f"       {detail}\n")

    print(f"Done: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
