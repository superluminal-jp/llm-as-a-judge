#!/usr/bin/env python3
"""Run multiple Lambda invocation patterns against a deployed LlmJudgeStack.

Uses Bedrock with ``amazon.nova-lite-v1:0`` in each payload (on-demand model).

Environment:
    AWS_REGION          Override region (default: config/parameters.json ``aws_region``).
    LAMBDA_FUNCTION_NAME  Skip CloudFormation lookup when set.

Usage (from repo root)::

    python3 scripts/lambda_pattern_tests.py
"""

from __future__ import annotations

import json
import os
import re
import sys
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


def _resolve_function_name(region: str) -> str:
    if name := os.environ.get("LAMBDA_FUNCTION_NAME", "").strip():
        return name
    import boto3

    cf = boto3.client("cloudformation", region_name=region)
    stacks = cf.describe_stacks(StackName="LlmJudgeStack")
    outs = stacks["Stacks"][0].get("Outputs") or []
    for o in outs:
        if o.get("OutputKey") == "LambdaFunctionName":
            return str(o["OutputValue"])
    raise RuntimeError("LambdaFunctionName output missing on LlmJudgeStack")


def _invoke(
    client: Any,
    name: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    raw = client.invoke(
        FunctionName=name,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )
    err = raw.get("FunctionError")
    body = json.loads(raw["Payload"].read().decode("utf-8"))
    return body, err


def main() -> int:
    params = _load_parameters()
    region = os.environ.get("AWS_REGION", params.get("aws_region", "ap-northeast-1"))
    bucket_arn = str(params.get("criteria_bucket_arn", "") or "")
    bucket = _bucket_from_arn(bucket_arn)

    import boto3

    lambda_client = boto3.client("lambda", region_name=region)
    fn = _resolve_function_name(region)

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
    print(f"Region={region} Function={fn}\n")

    for case_id, payload, expect_ok, note in cases:
        body, fn_err = _invoke(lambda_client, fn, payload)
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
