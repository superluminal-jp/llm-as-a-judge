# Research: AWS Lambda Minimal Restructure

**Phase 0 Output** | Date: 2026-03-01 | Branch: `001-lambda-minimal-restructure`

---

## 1. Structured Logging

**Decision:** AWS Lambda Powertools `Logger` を採用

**Rationale:**
- JSON 形式で CloudWatch Logs Insights に直接クエリ可能
- `@logger.inject_lambda_context` デコレーターが `aws_request_id`, `function_name`, `cold_start` を自動注入
- 標準 `logging` モジュールより設定ゼロで構造化ログを実現

**Key code pattern:**
```python
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

# モジュールレベルで初期化（コールドスタート時に一度だけ実行）
logger = Logger(service="llm-judge")

@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    logger.info("Evaluation started", extra={"provider": event.get("provider")})
```

**Alternatives:** 標準 `logging`（相関 ID 手動注入が必要）、手動 JSON ログ（冗長）

---

## 2. Error Handling

**Decision:** カスタム例外階層 + Lambda は例外を raise してそのまま伝播させる

**Rationale:**
- Lambda がエラーを JSON `{"errorType": ..., "errorMessage": ...}` に変換
- API Gateway の Lambda プロキシ統合でエラーレスポンスマッピング可能
- `logger.exception()` が自動的にスタックトレースを JSON に含める

**Exception hierarchy:**
```python
class LlmJudgeError(Exception):
    """Base exception."""

class ValidationError(LlmJudgeError):
    """Invalid input (missing fields, bad S3 URI, etc.)"""

class ConfigurationError(LlmJudgeError):
    """Missing env vars or misconfiguration."""

class ProviderError(LlmJudgeError):
    """LLM API call failed (auth, rate limit, timeout)."""

class CriteriaLoadError(LlmJudgeError):
    """S3 criteria file not found or invalid JSON."""
```

**Handler pattern:**
```python
try:
    result = evaluate(event)
    return result
except ValidationError as e:
    logger.warning("Validation failed", exc_info=True)
    raise  # Lambda formats as {"errorType": "ValidationError", "errorMessage": "..."}
except ProviderError as e:
    logger.error("Provider call failed", exc_info=True)
    raise
except Exception as e:
    logger.exception("Unexpected error")
    raise LlmJudgeError(f"Internal error: {e}") from e
```

**Alternatives:** try/except で dict を返す（API Gateway マッピングが複雑化）

---

## 3. Cold Start Optimization

**Decision:** SDK クライアントをモジュールレベルで初期化、LLM クライアントは遅延初期化

**Rationale:**
- boto3 S3 クライアントは常に必要 → モジュールレベル
- LLM プロバイダークライアント（Anthropic/OpenAI/Bedrock）はプロバイダーに応じて 1 つだけ使う → 遅延初期化でメモリ節約

**Pattern:**
```python
import boto3
from botocore.config import Config

# 常時使用するクライアント：モジュールレベルで初期化
_s3_client = boto3.client("s3", config=Config(max_pool_connections=10))

# LLM プロバイダー：遅延初期化でキャッシュ
_provider_cache: dict = {}

def get_provider(provider_name: str, config: Config) -> BaseProvider:
    if provider_name not in _provider_cache:
        _provider_cache[provider_name] = _create_provider(provider_name, config)
    return _provider_cache[provider_name]
```

**Alternatives:** ハンドラー内で毎回初期化（接続オーバーヘッド大）

---

## 4. S3 JSON File Loading

**Decision:** `boto3` S3 クライアント + `botocore.exceptions.ClientError` の error code 分岐

**Rationale:**
- `NoSuchKey` → `CriteriaLoadError`（404 相当）
- `AccessDenied` → `ConfigurationError`（IAM 設定ミス）
- その他 → `ProviderError`

**Pattern:**
```python
from botocore.exceptions import ClientError

def load_criteria_from_s3(s3_uri: str) -> dict:
    """Load criteria JSON from S3 URI (s3://bucket/key)."""
    bucket, key = _parse_s3_uri(s3_uri)
    try:
        resp = _s3_client.get_object(Bucket=bucket, Key=key)
        return json.loads(resp["Body"].read().decode("utf-8"))
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "NoSuchKey":
            raise CriteriaLoadError(f"Criteria file not found: {s3_uri}") from e
        elif code in ("AccessDenied", "403"):
            raise ConfigurationError(f"S3 access denied: {s3_uri}") from e
        raise ProviderError(f"S3 error ({code}): {s3_uri}") from e
    except json.JSONDecodeError as e:
        raise CriteriaLoadError(f"Invalid JSON in criteria file: {s3_uri}") from e
```

---

## 5. Environment Variable Config

**Decision:** `os.environ.get()` + コールドスタート時に必須項目を一括バリデーション

**Rationale:**
- `os.environ[key]` は KeyError を発生させ Lambda がエラー終了
- コールドスタート時に失敗させることで invocation ごとの重複チェックを排除

**Pattern:**
```python
import os

# モジュールレベルで読み込み（コールドスタート時のみ実行）
DEFAULT_PROVIDER = os.environ.get("DEFAULT_PROVIDER", "anthropic")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "30"))

def validate_config(provider: str) -> None:
    """Raise ConfigurationError if required env vars are missing."""
    if provider == "anthropic" and not ANTHROPIC_API_KEY:
        raise ConfigurationError("ANTHROPIC_API_KEY is required for anthropic provider")
    if provider == "openai" and not OPENAI_API_KEY:
        raise ConfigurationError("OPENAI_API_KEY is required for openai provider")
```

---

## 6. CDK Python Stack

**Decision:** `aws_cdk.aws_lambda.Function` + `Code.from_asset()` + `BundlingOptions`

**Rationale:**
- `PythonFunction`（alpha）は Docker 必須で CI 環境で重い
- `Code.from_asset()` + `pip install -t` で軽量バンドル可能
- 最小権限：Bedrock `InvokeModel`、S3 `GetObject`（criteria bucket のみ）

**Key patterns:**
```python
# cdk/stack.py
from aws_cdk import aws_lambda as lambda_, aws_iam as iam, Duration, Stack
from constructs import Construct

class LlmJudgeStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        fn = lambda_.Function(
            self, "LlmJudgeFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset(
                "../",
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=["bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && "
                        "cp -r src/* /asset-output"
                    ],
                ),
            ),
            memory_size=512,
            timeout=Duration.seconds(60),
            environment={
                "DEFAULT_PROVIDER": "anthropic",
                "LOG_LEVEL": "INFO",
            },
        )

        # Bedrock InvokeModel（Bedrock プロバイダー使用時）
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=["arn:aws:bedrock:*::foundation-model/*"],
        ))
```

**Secrets:** API キーは Secrets Manager → Lambda 環境変数に CDK で注入（`Secret.from_secret_name_v2`）

---

## 7. Testing Strategy

**Decision:** `pytest` + `unittest.mock` で LLM/S3 API をモック

**Pattern:**
```python
from unittest.mock import patch, MagicMock

def test_lambda_handler_success(mock_evaluator, mock_s3):
    event = {"prompt": "Q", "response": "A"}
    result = lambda_handler(event, MagicMock())
    assert "overall_score" in result

@patch("handler.load_criteria_from_s3")
def test_criteria_load_error(mock_s3):
    mock_s3.side_effect = CriteriaLoadError("not found")
    with pytest.raises(CriteriaLoadError):
        lambda_handler({"prompt": "Q", "response": "A",
                        "criteria_file": "s3://bad/key"}, MagicMock())
```

---

## 8. Sync vs Async

**Decision:** 完全同期実装（`asyncio` 不使用）

**Rationale:**
- Anthropic SDK は同期クライアント（`anthropic.Anthropic`）と非同期クライアント（`anthropic.AsyncAnthropic`）の両方を提供
- OpenAI SDK も同様に `OpenAI`（同期）/ `AsyncOpenAI`（非同期）
- Lambda の同期ハンドラーで `asyncio.run()` は動作するが不要なオーバーヘッドを生む
- 同期クライアントを使えばスレッドセーフかつシンプル

**Provider sync clients:**
- Anthropic: `anthropic.Anthropic(api_key=..., timeout=..., max_retries=...)`
- OpenAI: `openai.OpenAI(api_key=..., timeout=..., max_retries=...)`
- Bedrock: `boto3.client("bedrock-runtime", ...)` （元から同期）
