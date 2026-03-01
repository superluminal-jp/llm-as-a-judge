# Spec: AWS Lambda 関数への再構成とミニマル化

**種別**: リファクタリング（アーキテクチャ変更）
**日付**: 2026-03-01
**ステータス**: Approved

---

## 背景と問題

現在のシステムは DDD に基づく 4 層アーキテクチャと CLI インターフェースで構成されている。ファイル数は 60 以上に及び、以下の問題がある：

- **CLI インターフェース不要**: 実運用の呼び出し元は AWS イベントであり、CLI は不要
- **DDD の過剰設計**: Value Object、Repository、Specification 等の抽象化がユースケースの複雑さに対して過剰
- **保守コスト**: 機能追加・変更のたびに複数レイヤーをまたぐ修正が必要

---

## 変更内容

### 破棄するもの

- `presentation/` — CLI / FastAPI 全体
- `application/` — ユースケース・アプリケーションサービス層
- `domain/` — DDD ドメイン層全体
- `infrastructure/resilience/` — circuit_breaker（AWS SDK 標準リトライで代替）
- `infrastructure/persistence/` — JSON ファイル永続化
- `tests/` — 既存テスト全て（再作成）

### 保持・移植するもの

- LLM プロバイダークライアント（Anthropic / OpenAI / Bedrock）の API 呼び出しロジック
- 評価プロンプト構築・レスポンス解析ロジック
- 評価基準データ構造（EvaluationCriteria / CriterionDefinition / DefaultCriteria）

---

## ターゲット構成

```
src/
├── handler.py          # Lambda ハンドラー（同期関数）
├── evaluator.py        # 評価ロジック（プロンプト構築・LLM 呼び出し・結果解析）
├── criteria.py         # 評価基準定義（データクラス + DefaultCriteria）
├── config.py           # 設定（環境変数読み込み）
└── providers/
    ├── __init__.py
    ├── anthropic.py
    ├── openai.py
    └── bedrock.py
tests/
├── conftest.py
├── test_handler.py
├── test_evaluator.py
├── test_criteria.py
└── test_providers.py
cdk/
├── app.py              # CDK アプリエントリーポイント
├── stack.py            # Lambda スタック定義
└── requirements.txt    # CDK 依存ライブラリ
scripts/
└── deploy.sh           # デプロイスクリプト
requirements.txt        # Lambda 実行時依存ライブラリ
requirements-dev.txt    # 開発・テスト用依存ライブラリ
```

**ファイル数**: 17（現在 60+ → 約 75% 削減）

---

## Lambda ハンドラー仕様

### 関数シグネチャ

```python
def lambda_handler(event: dict, context) -> dict:
    ...
```

同期関数。`asyncio.run()` は使用しない。

### 入力イベント（JSON）

```json
{
  "prompt": "string（必須）",
  "response": "string（必須）",
  "criteria_file": "s3://bucket/key.json（オプション）",
  "provider": "anthropic | openai | bedrock（オプション）",
  "judge_model": "string（オプション）"
}
```

- `criteria_file`: S3 URI を指定。未指定時はデフォルト評価基準を使用
- `provider`: 未指定時は環境変数 `DEFAULT_PROVIDER` を参照
- `judge_model`: 未指定時は環境変数のモデル名を参照

### 成功レスポンス（JSON）

```json
{
  "overall_score": 4.2,
  "criterion_scores": {
    "accuracy": 4.5,
    "clarity": 4.0
  },
  "reasoning": "string",
  "judge_model": "string",
  "provider": "string"
}
```

### エラーレスポンス

例外を上位に伝播させる（API Gateway が HTTP ステータスに変換）。
Lambda 関数エラーとして以下の形式で返す：

```json
{
  "errorType": "ValidationError | ProviderError | ConfigurationError",
  "errorMessage": "string"
}
```

---

## criteria JSON ファイル仕様

```json
{
  "name": "My Criteria Set",
  "criteria": [
    {
      "name": "accuracy",
      "description": "Factual correctness of the response",
      "weight": 0.5,
      "evaluation_prompt": "Evaluate factual accuracy on a scale of 1-5"
    },
    {
      "name": "clarity",
      "description": "Clarity and readability",
      "weight": 0.5
    }
  ]
}
```

- `weight` は自動正規化（合計が 1.0 になるよう調整）
- `evaluation_prompt` はオプション

---

## 環境変数

| 変数名 | 必須 | デフォルト | 説明 |
|--------|------|-----------|------|
| `DEFAULT_PROVIDER` | No | `anthropic` | デフォルト LLM プロバイダー |
| `ANTHROPIC_API_KEY` | Conditional | — | Anthropic 利用時に必須 |
| `OPENAI_API_KEY` | Conditional | — | OpenAI 利用時に必須 |
| `AWS_REGION` | No | `us-east-1` | Bedrock 利用リージョン |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-20250514` | Anthropic モデル名 |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI モデル名 |
| `BEDROCK_MODEL` | No | `amazon.nova-premier-v1:0` | Bedrock モデル ID |
| `REQUEST_TIMEOUT` | No | `30` | API タイムアウト秒数 |

---

## CDK スタック仕様

- **Lambda**: Python 3.12、メモリ 512MB、タイムアウト 60 秒
- **IAM**: Bedrock `InvokeModel` 権限（Bedrock プロバイダー利用時）
- **環境変数**: CDK context または Secrets Manager から注入
- **デプロイ単位**: 単一スタック `LlmJudgeStack`

---

## デプロイスクリプト仕様（`scripts/deploy.sh`）

```
Usage: ./scripts/deploy.sh [--env dev|prod] [--region us-east-1]
```

実行内容：
1. 依存ライブラリのインストール（`pip install -r requirements.txt -t dist/`）
2. `cdk deploy` 実行
3. デプロイ後の Lambda ARN を標準出力

---

## 受け入れ条件

1. `handler.lambda_handler(event, context)` が上記 JSON 仕様を満たす（同期）
2. `provider` フィールドで Anthropic / OpenAI / Bedrock を切り替えられる
3. `criteria_file` 未指定時はデフォルト評価基準が適用される
4. `criteria_file` に S3 URI を指定した場合、該当 JSON を読み込んで評価に使用する
5. 必須フィールド（`prompt`, `response`）未指定時は `ValidationError` を発生させる
6. LLM API 呼び出し失敗時は `ProviderError` を発生させる
7. 全テストが `pytest` で通過する（モックを使用、実 API 呼び出しなし）
8. `cdk synth` が成功する
9. `scripts/deploy.sh` が引数なしで実行でき、CDK デプロイを完了する

---

## スコープ外

- API Gateway / ALB 等のトリガー設定（CDK スタックにオプションで追加可能だが、本スペックでは Lambda 単体のみ）
- 認証・認可
- バッチ処理（SQS トリガー等は別スペックで定義）
- モニタリング・アラート設定
- マルチリージョンデプロイ
