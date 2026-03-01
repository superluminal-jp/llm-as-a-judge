# Implementation Plan: Lambda Minimal Restructure

**Branch**: `001-lambda-minimal-restructure` | **Date**: 2026-03-01
**Spec**: `specs/001-lambda-minimal-restructure/spec.md`

---

## Summary

現在の DDD + CLI 構成（60+ ファイル）を AWS Lambda 向けフラット構成（8 ソースファイル）に再構成する。
コアロジック（LLM プロバイダー呼び出し・評価プロンプト構築・基準定義）を移植し、
AWS Lambda Powertools による構造化ログ・エラーハンドリング・CDK デプロイを追加する。

---

## Technical Context

| 項目 | 内容 |
|------|------|
| **Language/Version** | Python 3.12 |
| **Lambda Runtime** | `python3.12` |
| **Primary Dependencies** | `anthropic`, `openai`, `boto3`, `aws-lambda-powertools` |
| **Testing** | `pytest` + `unittest.mock`（実 API 呼び出しなし） |
| **IaC** | AWS CDK v2（Python） |
| **Logging** | AWS Lambda Powertools `Logger`（JSON 構造化ログ） |
| **Target Platform** | AWS Lambda + API Gateway（オプション） |
| **Performance Goals** | コールドスタート < 3 秒、p95 レイテンシ < Lambda タイムアウト（60 秒） |
| **Constraints** | ステートレス、ファイルシステム永続化なし、デプロイパッケージ < 50MB |

---

## Constitution Check

| ゲート | 状態 | 備考 |
|--------|------|------|
| 最小限の構造 | ✅ | フラット 5 ファイル構成。DDD 廃止 |
| テスト可能性 | ✅ | 全モジュールをモックでユニットテスト可能 |
| 同期実装 | ✅ | asyncio 不使用。LLM SDK の同期クライアントを使用 |
| ステートレス | ✅ | ファイル永続化なし |
| ベストプラクティス | ✅ | Powertools Logger / エラー階層 / コールドスタート最適化 |

---

## Project Structure

### Documentation (this feature)

```
specs/001-lambda-minimal-restructure/
├── spec.md              ✅
├── research.md          ✅
├── data-model.md        ✅
├── plan.md              ✅ (このファイル)
├── contracts/
│   ├── lambda-event.json    ✅
│   ├── lambda-response.json ✅
│   └── criteria-file.json   ✅
└── tasks.md             （/speckit.tasks で生成）
```

### Source Code (repository root after refactoring)

```
src/
├── handler.py          # Lambda エントリーポイント・例外定義
├── evaluator.py        # プロンプト構築・LLM 呼び出し・結果解析
├── criteria.py         # EvaluationCriteria / CriterionDefinition / S3 ロード
├── config.py           # 環境変数読み込み・Config dataclass
└── providers/
    ├── __init__.py     # BaseProvider プロトコル + get_provider() ファクトリ
    ├── anthropic.py    # 同期 Anthropic クライアント
    ├── openai.py       # 同期 OpenAI クライアント
    └── bedrock.py      # Bedrock クライアント（boto3）

tests/
├── conftest.py         # 共通フィクスチャ（モック LLM レスポンス等）
├── test_handler.py     # lambda_handler() のテスト
├── test_evaluator.py   # プロンプト構築・レスポンス解析のテスト
├── test_criteria.py    # EvaluationCriteria・S3 ロードのテスト
└── test_providers.py   # 各プロバイダークライアントのテスト

cdk/
├── app.py              # CDK App エントリーポイント
├── stack.py            # LlmJudgeStack（Lambda + IAM + 環境変数）
└── requirements.txt    # CDK 依存（aws-cdk-lib, constructs）

scripts/
└── deploy.sh           # デプロイスクリプト（bootstrap + cdk deploy）

requirements.txt        # Lambda ランタイム依存
requirements-dev.txt    # 開発・テスト依存（pytest, pytest-cov, moto）
cdk.json                # CDK アプリ設定
```

---

## モジュール設計詳細

### `src/handler.py` — Lambda エントリーポイント

**責務**: イベントバリデーション・オーケストレーション・例外定義

```python
"""AWS Lambda handler for LLM-as-a-Judge evaluation.

Entry point for the Lambda function. Validates input, loads criteria,
and delegates evaluation to the evaluator module.

Exceptions defined here are the single source of truth for the
error hierarchy used across all modules.
"""
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger(service="llm-judge")

# --- Exception Hierarchy ---
class LlmJudgeError(Exception):
    """Base exception for all llm-judge errors."""

class ValidationError(LlmJudgeError):
    """Raised when input event is invalid (missing fields, bad format)."""

class ConfigurationError(LlmJudgeError):
    """Raised when required env vars are missing or values are invalid."""

class ProviderError(LlmJudgeError):
    """Raised when LLM provider API call fails (auth, rate limit, timeout)."""

class CriteriaLoadError(LlmJudgeError):
    """Raised when criteria cannot be loaded from S3."""


@logger.inject_lambda_context(log_event=False)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Evaluate an LLM response using a judge LLM.

    Args:
        event: Lambda invocation event. See contracts/lambda-event.json.
        context: Lambda context object provided by the runtime.

    Returns:
        Evaluation result. See contracts/lambda-response.json.

    Raises:
        ValidationError: Required fields missing or malformed.
        ConfigurationError: Required environment variables not set.
        ProviderError: LLM API call failed.
        CriteriaLoadError: S3 criteria file not accessible or invalid.
    """
```

---

### `src/config.py` — 設定管理

**責務**: 環境変数の読み込みとバリデーション

- モジュールレベルで `Config` を生成（コールドスタートで 1 回だけ実行）
- `validate_for_provider(provider)` でプロバイダーごとの必須チェック
- `dataclass(frozen=True)` でイミュータブル

---

### `src/criteria.py` — 評価基準

**責務**: 基準データ構造の定義と S3 からのロード

移植元: `domain/evaluation/criteria.py`

**残すもの:**
- `CriterionDefinition` (frozen dataclass)
- `EvaluationCriteria` (weight 正規化ロジック含む)
- `DefaultCriteria.balanced()` のみ

**新規追加:**
- `load_from_s3(s3_uri: str) -> EvaluationCriteria` — S3 URI をパースして boto3 で取得
- `load_from_dict(data: dict) -> EvaluationCriteria` — JSON dict から構築

**削除:**
- `CriteriaBuilder`, `CriteriaParser.parse_criteria_string()`, `WeightConfigParser`
- `create_criteria_template()`, `save_criteria_template()`

---

### `src/providers/__init__.py` — プロバイダーファクトリ

**責務**: プロバイダーの抽象化とキャッシュ

```python
"""Provider protocol and factory with cold-start caching.

Each provider is initialized once per Lambda container lifetime
and reused across invocations.
"""
from typing import Protocol, runtime_checkable

@runtime_checkable
class BaseProvider(Protocol):
    def complete(
        self,
        messages: list[dict],
        model: str,
        timeout: int,
    ) -> str:
        """Send messages to LLM and return raw text response.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            model: Model name/ID to use.
            timeout: Request timeout in seconds.

        Returns:
            Raw text content from the LLM response.

        Raises:
            ProviderError: If the API call fails.
        """
        ...

# Cold-start: provider instances cached per container
_cache: dict[str, BaseProvider] = {}

def get_provider(name: str, config) -> BaseProvider:
    """Return cached provider instance, creating if not present."""
    if name not in _cache:
        _cache[name] = _create(name, config)
    return _cache[name]
```

---

### `src/providers/anthropic.py` — Anthropic クライアント

移植元: `infrastructure/clients/anthropic_client.py`

**変更点:**
- `async def` → `def`（同期）
- `anthropic.AsyncAnthropic` → `anthropic.Anthropic`
- `EnhancedRetryManager` 削除 → SDK の `max_retries=3` で代替
- `ProviderTimeoutManager` 削除 → SDK の `timeout=` パラメータで代替
- Powertools Logger 使用

**コールドスタート最適化:**
```python
# Cold-start: Anthropic client initialized once per container.
# The SDK maintains an internal HTTP connection pool, which is
# reused across Lambda invocations in the same container.
_client: anthropic.Anthropic | None = None
```

---

### `src/providers/openai.py` / `src/providers/bedrock.py`

同様のパターンで移植。

---

### `src/evaluator.py` — 評価ロジック

移植元: `infrastructure/clients/multi_criteria_client.py`

**責務**: プロンプト構築・LLM 呼び出し・JSON パース・スコア集計

```python
"""Core evaluation logic for multi-criteria LLM assessment.

Builds structured prompts, calls the judge LLM, parses JSON responses,
and aggregates criterion scores into an overall result.
"""

def evaluate(
    prompt: str,
    response: str,
    criteria: EvaluationCriteria,
    provider: BaseProvider,
    model: str,
    timeout: int,
) -> dict:
    """Run multi-criteria evaluation and return result dict.

    Args:
        prompt: The original question/prompt given to the evaluated LLM.
        response: The LLM response to evaluate.
        criteria: Evaluation criteria with weights.
        provider: LLM provider client implementing BaseProvider.
        model: Judge model name.
        timeout: API request timeout in seconds.

    Returns:
        Dict matching contracts/lambda-response.json schema.

    Raises:
        ProviderError: If LLM API call fails.
    """
```

---

### `cdk/stack.py` — CDK スタック

```python
"""CDK stack for LLM-as-a-Judge Lambda deployment.

Deploys a single Lambda function with:
- Python 3.12 runtime
- 512MB memory, 60s timeout
- IAM: bedrock:InvokeModel, s3:GetObject (for criteria)
- Environment variables from CDK context
"""
```

**IAM 最小権限:**
- `bedrock:InvokeModel` → `arn:aws:bedrock:*::foundation-model/*`
- `s3:GetObject` → `arn:aws:s3:::${criteria_bucket_arn}/*`（context で指定）
- CloudWatch Logs は Lambda 実行ロールが自動付与

**API キー管理:**
- Anthropic/OpenAI の API キーは **Secrets Manager** から取得
- CDK で `secretsmanager:GetSecretValue` 権限を付与
- Lambda 起動時に Secrets Manager から取得（コールドスタートで 1 回）

---

### `scripts/deploy.sh`

```bash
#!/bin/bash
set -euo pipefail

# Usage: ./scripts/deploy.sh [--env dev|prod] [--region us-east-1]
# Environment variables: AWS_REGION, AWS_ACCOUNT_ID, CRITERIA_BUCKET_ARN (optional)
```

実行ステップ:
1. AWS 認証確認（`aws sts get-caller-identity`）
2. CDK 依存インストール（`pip install -r cdk/requirements.txt`）
3. CDK Bootstrap（冪等）
4. `cdk deploy LlmJudgeStack --require-approval never`
5. Lambda ARN を標準出力

---

## ロギング規約

| レベル | 使用場面 |
|--------|---------|
| `logger.debug()` | プロンプト内容・LLM 生レスポンス（`LOG_LEVEL=DEBUG` 時のみ） |
| `logger.info()` | 評価開始・完了・使用モデル・スコアサマリー |
| `logger.warning()` | JSON パース失敗・フォールバック発生 |
| `logger.error(..., exc_info=True)` | 回復不能エラー（raise 前） |
| `logger.exception()` | 予期しない例外（スタックトレース自動付与） |

全ログに自動付与されるフィールド（Powertools）:
`timestamp`, `level`, `service`, `aws_request_id`, `function_name`, `cold_start`

---

## エラーハンドリング規約

1. **例外は raise**: `return {"error": ...}` でなく例外を raise する
2. **ログ後に raise**: `logger.error(..., exc_info=True)` → `raise`
3. **原因連鎖**: `raise ProviderError("...") from original_exception`
4. **汎用例外の変換**: `except Exception as e: raise LlmJudgeError("Internal error") from e`

---

## コメント規約

- **モジュール**: 責務・主要クラス/関数・注意事項を docstring に記述
- **関数**: Google スタイル docstring（Args / Returns / Raises）
- **コールドスタート最適化箇所**: `# Cold-start: ...` コメントで意図を明示
- **複雑なロジック**: "なぜ" を説明するインラインコメント（"何を" は不要）

---

## 依存ライブラリ

### `requirements.txt`（Lambda ランタイム）
```
anthropic>=0.40.0
openai>=1.60.0
boto3>=1.35.0
aws-lambda-powertools>=3.0.0
```

### `requirements-dev.txt`（開発・テスト）
```
pytest>=8.0.0
pytest-cov>=6.0.0
moto[s3]>=5.0.0
```

### `cdk/requirements.txt`（CDK）
```
aws-cdk-lib>=2.170.0
constructs>=10.0.0
```

---

## 削除対象

```
src/llm_judge/                  # DDD パッケージ全体
tests/unit/                     # 全ユニットテスト（再作成）
tests/integration/              # 全統合テスト（再作成）
```

---

## Complexity Tracking

| 削除した複雑さ | 理由 |
|--------------|------|
| DDD 4 層構造 | Lambda の単一責務に対して過剰 |
| EnhancedRetryManager / CircuitBreaker | SDK 組み込みリトライで十分 |
| PersistenceService（JSON ファイル） | Lambda のステートレス性に違反 |
| CLI インターフェース（argparse） | Lambda イベントが唯一の入力 |
| asyncio 全体 | 同期 SDK で代替可能 |
| domain_events / specifications | 使われていない抽象化 |
