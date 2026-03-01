# Data Model: AWS Lambda Minimal Restructure

**Phase 1 Output** | Date: 2026-03-01

---

## Entities

### 1. `EvaluationRequest` (Lambda イベント入力)

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `prompt` | `str` | ✅ | 評価対象のプロンプト |
| `response` | `str` | ✅ | 評価対象の LLM 応答 |
| `criteria_file` | `str \| None` | — | S3 URI（例: `s3://bucket/key.json`） |
| `provider` | `str \| None` | — | `"anthropic"` \| `"openai"` \| `"bedrock"` |
| `judge_model` | `str \| None` | — | プロバイダー固有モデル名 |

**バリデーションルール:**
- `prompt` と `response` は空文字列不可
- `criteria_file` が指定される場合、`s3://` で始まる URI
- `provider` が指定される場合、許可された 3 値のいずれか

---

### 2. `CriterionDefinition` (評価基準の単一項目)

| フィールド | 型 | 必須 | デフォルト | 説明 |
|-----------|-----|------|-----------|------|
| `name` | `str` | ✅ | — | 基準名（英数字アンダースコア） |
| `description` | `str` | ✅ | — | 基準の説明 |
| `weight` | `float` | — | `1.0` | 重み（正規化前） |
| `scale_min` | `int` | — | `1` | スコア最小値 |
| `scale_max` | `int` | — | `5` | スコア最大値 |
| `evaluation_prompt` | `str` | — | `""` | LLM へのガイダンス |
| `examples` | `dict[int, str]` | — | `{}` | スコア → 例 |

**バリデーションルール:**
- `weight > 0`
- `scale_min < scale_max`
- `name` は空文字列不可

---

### 3. `EvaluationCriteria` (評価基準コレクション)

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `criteria` | `list[CriterionDefinition]` | 1 件以上 |
| `name` | `str` | 基準セット名 |
| `description` | `str` | 説明 |

**ビジネスルール:**
- `criteria` が 1 件未満は無効
- 正規化後の `weight` 合計 ≒ 1.0

---

### 4. `CriterionScore` (1 基準のスコア)

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `criterion_name` | `str` | 対応する基準名 |
| `score` | `int` | 1–5 の整数スコア |
| `reasoning` | `str` | スコアの根拠 |
| `confidence` | `float` | 0.0–1.0 |
| `weight` | `float` | 正規化済み重み |

---

### 5. `EvaluationResult` (Lambda 出力)

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `overall_score` | `float` | 加重平均スコア（1.0–5.0） |
| `criterion_scores` | `dict[str, float]` | 基準名 → スコア |
| `reasoning` | `str` | 総合評価コメント |
| `judge_model` | `str` | 使用したモデル名 |
| `provider` | `str` | 使用したプロバイダー |

---

## 設定 (Config)

モジュールレベルで読み込み、コールドスタート時に一度だけ評価。

| 変数 | 型 | デフォルト | 説明 |
|------|-----|-----------|------|
| `DEFAULT_PROVIDER` | `str` | `"anthropic"` | プロバイダー |
| `ANTHROPIC_API_KEY` | `str \| None` | `None` | Anthropic キー |
| `OPENAI_API_KEY` | `str \| None` | `None` | OpenAI キー |
| `AWS_REGION` | `str` | `"us-east-1"` | Bedrock リージョン |
| `ANTHROPIC_MODEL` | `str` | `"claude-sonnet-4-20250514"` | モデル名 |
| `OPENAI_MODEL` | `str` | `"gpt-4o"` | モデル名 |
| `BEDROCK_MODEL` | `str` | `"amazon.nova-premier-v1:0"` | モデル ID |
| `REQUEST_TIMEOUT` | `int` | `30` | タイムアウト秒 |

---

## 例外階層

```
LlmJudgeError (base)
├── ValidationError     - 入力値不正（必須フィールド欠落、不正な S3 URI 等）
├── ConfigurationError  - 環境変数不足・設定ミス
├── ProviderError       - LLM API 呼び出し失敗（認証・レート制限・タイムアウト）
└── CriteriaLoadError   - S3 からの criteria ファイル読み込み失敗
```

---

## データフロー

```
Lambda Event (dict)
    │
    ▼
handler.lambda_handler()
    │  バリデーション（prompt, response 必須チェック）
    │  プロバイダー選択（event["provider"] or DEFAULT_PROVIDER）
    │  criteria ロード（S3 or デフォルト）
    ▼
evaluator.evaluate()
    │  プロンプト構築（_build_multi_criteria_prompt）
    │  LLM 呼び出し（provider.complete()）
    │  レスポンス解析（_parse_multi_criteria_response）
    ▼
EvaluationResult (dict)
```

---

## criteria.json ファイルスキーマ (S3 から読み込む JSON)

```json
{
  "name": "string (optional)",
  "criteria": [
    {
      "name": "string (required)",
      "description": "string (required)",
      "weight": 1.0,
      "evaluation_prompt": "string (optional)",
      "examples": {
        "1": "string",
        "5": "string"
      }
    }
  ]
}
```
