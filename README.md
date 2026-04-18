# LLM-as-a-Judge

[![Tests](https://img.shields.io/badge/tests-94%20passing-brightgreen)](#テスト)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://python.org)
[![AWS Lambda](https://img.shields.io/badge/runtime-AWS%20Lambda-orange)](https://aws.amazon.com/lambda/)

LLM が生成した回答を、別の LLM を審査役（ジャッジ）として多角的に評価する AWS Lambda 関数。Anthropic・OpenAI・Amazon Bedrock をジャッジモデルとして利用可能。

各クライテリアを並列に独立評価し、段階的推論（`evaluation_steps`）によって透明性の高いスコアリングを実現する。

## ドキュメント

| リソース | 内容 |
|----------|------|
| **[docs/quickstart.md](docs/quickstart.md)** | 最短でテスト→デプロイ→呼び出し |
| **[docs/README.md](docs/README.md)** | 索引（アーキテクチャ・開発・トラブルシューティング・JSON 契約の場所） |
| [docs/repository-layout.md](docs/repository-layout.md) | `src` / `tests` / `scripts` / `cdk` / `contracts` の役割 |
| [docs/architecture.md](docs/architecture.md) | 処理の流れとモジュールの役割 |
| [docs/development.md](docs/development.md) | 依存関係・テスト・ディレクトリの読み方 |
| [docs/troubleshooting.md](docs/troubleshooting.md) | 典型障害の切り分け |
| [docs/schemas.md](docs/schemas.md) | Lambda／クライテリアの JSON Schema パスと注意点 |
| [config/README.md](config/README.md) | デプロイパラメータ（`parameters.json`） |

## アーキテクチャ

```
Lambda イベント (prompt, response, [provider], [criteria_file])
    └─→ handler.lambda_handler
        ├─→ criteria.load_from_s3()   または   DefaultCriteria.balanced()
        ├─→ providers.get_provider()  → AnthropicProvider / OpenAIProvider / BedrockProvider
        └─→ evaluator.evaluate()
              ├─→ build_evaluation_prompt_single_criterion()  ← クライテリアごとに並列実行
              ├─→ provider.complete()
              └─→ parse_single_criterion_response()
                  └─→ { criterion_scores, criterion_reasoning, reasoning, judge_model, provider }
```

各クライテリアは独立した LLM 呼び出しでスコアリングされ、総合スコアは算出しない（クライテリア間の重み付けを前提としない設計）。

## プロジェクト構造

```
src/
├── __init__.py
├── handler.py          # Lambda エントリポイント、例外階層
├── evaluator.py        # プロンプト構築、LLM 呼び出し、JSON パース、スコア集約
├── criteria.py         # EvaluationCriteria データクラス、S3 ローダー、デフォルト定義
├── config.py           # 環境変数ベースの Config（コールドスタートキャッシュ付き）
└── providers/
    ├── __init__.py     # BaseProvider プロトコル + get_provider() ファクトリ
    ├── anthropic.py    # 同期 Anthropic クライアント
    ├── openai.py       # 同期 OpenAI クライアント
    └── bedrock.py      # Bedrock Converse API（IAM 認証）

criteria/
├── default.json                          # 汎用評価クライテリア（7 軸）
├── disclosure_evaluation_criteria.json   # 情報公開法第 5 条評価基準（6 条号）
└── aisi_safety_evaluation_criteria.json  # AISI AIセーフティ評価観点（10 軸）

examples/
├── default_evaluation_result.json      # default.json を使った評価 I/O サンプル
└── disclosure_evaluation_result.json   # 情報公開法評価 I/O サンプル

contracts/
├── lambda-event.json      # Lambda 入力（JSON Schema）
├── lambda-response.json   # Lambda 成功レスポンス
└── criteria-file.json     # S3 クライテリア JSON

tests/
├── conftest.py         # 共有フィクスチャ
├── test_handler.py     # lambda_handler() テスト
├── test_evaluator.py   # プロンプト構築・レスポンスパーステスト
├── test_criteria.py    # EvaluationCriteria・S3 ローダーテスト
└── test_providers.py   # プロバイダークライアントテスト

config/
├── parameters.json         # デプロイ・CDK 用パラメータ（リージョン、default_provider、criteria バケット ARN 等）
├── parameters.example.json # テンプレート
└── README.md               # パラメータの説明

cdk/
├── app.py              # CDK App エントリポイント
├── stack.py            # LlmJudgeStack（Lambda + IAM + 環境変数）
└── requirements.txt    # CDK 依存関係

scripts/
└── deploy.sh           # Bootstrap + cdk deploy ラッパー

docs/
├── README.md              # ドキュメント索引
├── quickstart.md          # 最短の試し方（テスト・デプロイ・invoke）
├── repository-layout.md   # src / tests / scripts / cdk / contracts
├── architecture.md        # 処理フロー・モジュール役割
├── development.md         # 開発・テスト
├── troubleshooting.md     # 運用時の切り分け
└── schemas.md             # JSON 契約（`contracts/*.json`）
```

## Lambda イベント

```json
{
  "prompt": "機械学習とは何ですか？",
  "response": "機械学習とは、データから自動的に学習するAIの一分野です...",
  "provider": "bedrock",
  "judge_model": "amazon.nova-lite-v1:0",
  "criteria_file": "s3://my-bucket/criteria/custom.json",
  "system_prompt": "あなたは機械学習の専門家として回答してください。",
  "contexts": ["参考資料1: 機械学習の歴史...", "参考資料2: 主要なアルゴリズム..."]
}
```

| フィールド | 型 | 必須 | デフォルト | 説明 |
|-----------|-----|------|-----------|------|
| `prompt` | `string` | ✅ | — | 評価対象 LLM に与えたプロンプト |
| `response` | `string` | ✅ | — | 評価対象 LLM の回答 |
| `provider` | `string` | ✗ | `DEFAULT_PROVIDER` 環境変数 | `anthropic` / `openai` / `bedrock` |
| `judge_model` | `string` | ✗ | プロバイダー別デフォルトモデル | ジャッジに使用するモデル ID |
| `criteria_file` | `string` | ✗ | デフォルト balanced クライテリア | **事前に S3 にアップロード**した JSON の URI（例: `s3://bucket/criteria.json`）。ローカルパスは不可 |
| `system_prompt` | `string` | ✗ | `null` | 評価対象 LLM に与えたシステムプロンプト。ジャッジプロンプトに挿入され、指示追従性の評価に利用される |
| `contexts` | `string` または `string[]` | ✗ | `null` | 評価時に参照する追加コンテキスト（RAG 取得ドキュメント等）。複数指定時は `[1]`, `[2]` 番号付きで挿入される |

## Lambda レスポンス

```json
{
  "criterion_scores": {
    "accuracy": 4.5,
    "clarity": 4.0,
    "helpfulness": 4.0,
    "completeness": 3.5
  },
  "criterion_reasoning": {
    "accuracy": "Step 1: Yes, all claims are verifiable.\nStep 2: No contradictions found.\nStep 3: No speculation presented as fact.\n\nFinal: 事実の正確性は高く、主要な主張はすべて検証可能。",
    "clarity": "Step 1: Logical structure is clear.\nStep 2: No ambiguous statements.\nStep 3: Complexity is appropriate.\n\nFinal: 全体的に明快で読みやすい構成。",
    "helpfulness": "Step 1: Actionable information provided.\nStep 2: Common follow-up questions addressed.\nStep 3: Calibrated to audience level.\n\nFinal: 実用的な情報が含まれており有用性が高い。",
    "completeness": "Step 1: Most aspects addressed.\nStep 2: Some omissions present.\nStep 3: Depth is adequate for key points.\n\nFinal: 主要な観点は網羅されているが、応用例の説明が不足。"
  },
  "reasoning": "総評: 各クライテリアの評価結果は以下のとおりである。accuracy 4.5, clarity 4.0, helpfulness 4.0, completeness 3.5。各観点は独立した意味を持つため総合スコアは算出していない。",
  "judge_model": "claude-sonnet-4-6",
  "provider": "anthropic"
}
```

### フィールド説明

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `criterion_scores` | `object` | クライテリア名 → スコア（1〜5）のマッピング |
| `criterion_reasoning` | `object` | クライテリア名 → 推論テキストのマッピング。`evaluation_steps` が定義されている場合は各ステップの回答と最終判断を含む |
| `reasoning` | `string` | 全クライテリアをまとめた総評 |
| `judge_model` | `string` | 使用したジャッジモデル名 |
| `provider` | `string` | 使用したプロバイダー（`anthropic` / `openai` / `bedrock`） |

> 総合スコア（`overall_score`）は算出しない。各クライテリアは独立した意味を持つ。

## クライテリアファイル（S3）

カスタム評価クライテリアは **S3 上の JSON ファイル** として配置し、Lambda イベントの `criteria_file` に S3 URI（例: `s3://my-bucket/criteria/custom.json`）を渡して使用する。リポジトリ直下の `criteria/*.json` は編集・レビュー・バージョン管理用であり、**実行時は必ず S3 にアップロードしたオブジェクトが参照される**（ローカルパスは指定不可）。`criteria_file` を省略した場合のみ、組み込みの Balanced クライテリア（4 軸）が使われる。

```bash
# アップロード例
aws s3 cp criteria/default.json s3://my-bucket/criteria/default.json
```

### 基本形式

```json
{
  "name": "技術評価クライテリア",
  "criteria": [
    {
      "name": "accuracy",
      "description": "回答の事実的正確性",
      "evaluation_prompt": "すべての技術的主張が正確かどうかを評価してください",
      "score_descriptors": {
        "1": "重大な事実誤りが含まれる",
        "3": "概ね正確だが小さな誤りがある",
        "5": "完全に正確で根拠が明示されている"
      }
    }
  ]
}
```

### 段階的推論（evaluation_steps）

`evaluation_steps` を定義すると、ジャッジ LLM が各ステップを順番に回答してから最終スコアを出力する。推論の透明性が向上し、複雑な評価基準（法的判断など）に特に有効。

```json
{
  "name": "accuracy",
  "description": "回答の事実的正確性",
  "evaluation_steps": [
    "すべての事実的主張は検証可能で根拠が示されているか？",
    "回答内に矛盾や不整合はないか？",
    "推測や意見が事実として提示されていないか？"
  ],
  "score_descriptors": {
    "1": "重大な事実誤りが含まれる",
    "5": "完全に正確で根拠が明示されている"
  }
}
```

`evaluation_steps` があると `criterion_reasoning` は以下の形式になる：

```
Step 1: Yes, all claims are verifiable and cited.
Step 2: No contradictions found.
Step 3: No speculation presented as fact.

Final: 事実の正確性は高く、主要な主張はすべて検証可能。
```

### クライテリアフィールド一覧

| フィールド | 必須 | 説明 |
|-----------|------|------|
| `name` | ✅ | 識別子（英数字・アンダースコアのみ） |
| `description` | ✅ | このクライテリアが測定する内容 |
| `evaluation_prompt` | ✗ | ジャッジ LLM への追加ガイダンス |
| `evaluation_steps` | ✗ | ステップバイステップの評価チェックリスト |
| `score_descriptors` | ✗ | スコア値 → 説明テキストのマッピング |

Lambda 実行ロールに対象バケットの `s3:GetObject` が必要（[`config/parameters.json`](config/parameters.json) の `criteria_bucket_arn` または CDK `--context` で付与）。

## 環境変数

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `DEFAULT_PROVIDER` | `bedrock` | イベントで `provider` 未指定時のプロバイダー |
| `ANTHROPIC_API_KEY` | — | Anthropic 利用時に必須 |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | デフォルト Anthropic ジャッジモデル |
| `OPENAI_API_KEY` | — | OpenAI 利用時に必須 |
| `OPENAI_MODEL` | `gpt-4o` | デフォルト OpenAI ジャッジモデル |
| `BEDROCK_MODEL` | `anthropic.claude-sonnet-4-6` | デフォルト Bedrock ジャッジモデル |
| `REQUEST_TIMEOUT` | `30` | HTTP タイムアウト（秒） |
| `LOG_LEVEL` | `INFO` | Powertools ログレベル |
| `POWERTOOLS_SERVICE_NAME` | `llm-judge` | Lambda Powertools サービスタグ |

> Bedrock は Lambda 実行ロールの IAM 認証を使用するため、API キー不要。

## エラーハンドリング

すべてのエラーは例外として伝播する（`return {"error": ...}` は使用しない）。

| 例外 | 原因 |
|------|------|
| `ValidationError` | 必須フィールド欠損・不正な形式 |
| `ConfigurationError` | API キー未設定・未知のプロバイダー |
| `ProviderError` | LLM API 呼び出し失敗（認証・レート制限・パースエラー） |
| `CriteriaLoadError` | S3 オブジェクト未存在・無効な JSON |

## ローカル開発

```bash
# 依存関係インストール
pip install -r requirements.txt -r requirements-dev.txt

# 全テスト実行
pytest

# カバレッジレポート付き
pytest --cov=src --cov-report=term-missing

# 特定のテストファイルのみ
pytest tests/test_evaluator.py -v
```

## デプロイ

### 前提条件

- AWS CLI（適切な認証情報が設定済み）
- CDK CLI: `npm install -g aws-cdk`
- Docker（**必須** — `cdk synth` / `cdk deploy` 時の Lambda アセットバンドルに使用。デーモンが起動していること）

### クイックデプロイ

```bash
# 環境変数を設定
export ANTHROPIC_API_KEY=sk-ant-...   # Anthropic を使う場合

# デプロイ（初回は CDK bootstrap を自動実行）
./scripts/deploy.sh

# リージョン指定
./scripts/deploy.sh --region us-east-1   # 既定は ap-northeast-1

# S3 クライテリアバケットアクセスを付与してデプロイ
CRITERIA_BUCKET_ARN=arn:aws:s3:::my-bucket ./scripts/deploy.sh
```

### パラメータファイル

リポジトリ直下の [`config/parameters.json`](config/parameters.json) で `aws_region`・`default_provider`・`criteria_bucket_arn` などを指定する（[`config/README.md`](config/README.md) 参照）。`cdk deploy` の `--context` は同じキーを上書きできる。

### 手動 CDK デプロイ

```bash
pip install -r cdk/requirements.txt
cdk bootstrap
cdk deploy LlmJudgeStack \
  --app "python3 cdk/app.py" \
  --require-approval never \
  --context criteria_bucket_arn=arn:aws:s3:::my-bucket
```

### デプロイ後の API キー設定

```bash
aws lambda update-function-configuration \
  --function-name <function-name> \
  --environment "Variables={ANTHROPIC_API_KEY=sk-ant-...,DEFAULT_PROVIDER=anthropic}"
```

### Lambda 呼び出し

```bash
aws lambda invoke \
  --function-name <function-name> \
  --payload '{"prompt":"機械学習とは何ですか？","response":"機械学習はAIの一分野です...","provider":"bedrock"}' \
  --cli-binary-format raw-in-base64-out \
  result.json && cat result.json
```

## テスト

94 テスト、実際の API 呼び出しなし（`unittest.mock` + `moto[s3]` でモック）：

```bash
pytest                                         # 全テスト
pytest tests/test_handler.py -v               # ハンドラーテスト
pytest tests/test_evaluator.py -v             # 評価ロジックテスト
pytest tests/test_criteria.py -v              # クライテリア・S3 テスト
pytest tests/test_providers.py -v             # プロバイダーテスト
pytest --cov=src --cov-report=term-missing    # カバレッジ付き（src 合計約 88%）
```

## CDK スタックリソース

- **Lambda 関数**: Python 3.12、512 MB、60 秒タイムアウト
- **バンドル**: CDK が公式 Python 3.12 イメージ上で `pip install` と `src/` のコピーを実行（Docker 必須）
- **IAM ポリシー**: すべての基盤モデルに対する `bedrock:InvokeModel` + `bedrock:Converse`
- **IAM ポリシー**（オプション）: クライテリアバケットへの `s3:GetObject`
- **CloudWatch Logs**: Lambda ランタイムが自動作成
- **Outputs**: `LambdaFunctionArn`、`LambdaFunctionName`
