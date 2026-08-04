# LLM-as-a-Judge

[![Tests](https://img.shields.io/badge/tests-201%20passing-brightgreen)](#テスト)
[![Python](https://img.shields.io/badge/python-3.13-blue)](https://python.org)
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

同じイベントを受け付け、**同じレスポンス**を返す実行経路が 2 つある。

**経路 1: 単一 Lambda**（`aws lambda invoke`）

```
Lambda イベント（`prompt` / `response` は少なくとも一方必須、[provider]、[criteria_file]、任意 descriptor）
    └─→ handler.lambda_handler
        ├─→ criteria.load_from_s3()   または   DefaultCriteria.balanced()
        ├─→ providers.get_provider()  → AnthropicProvider / OpenAIProvider / BedrockProvider
        └─→ evaluator.evaluate()
              ├─→ build_evaluation_prompt_single_criterion()  ← 最大 MAX_PARALLEL_CRITERIA 並列
              ├─→ provider.complete()
              └─→ parse_single_criterion_response()
                  └─→ { criterion_scores, criterion_reasoning, criterion_assessability, reasoning, judge_model, provider }
```

**経路 2: Step Functions ワークフロー**（`aws stepfunctions start-sync-execution`）

```
Prepare → Map(MaxConcurrency)[EvaluateCriterion] → Summarize
```

クライテリア単位のリトライ（バックオフ + FULL jitter）と失敗箇所の可視化をサービス側に任せられる。
payload は 256KB のステート上限を避けるため S3 経由（クレームチェック）で渡す。
クライテリア数が多い場合はこちらを使う。詳細は [docs/architecture.md](docs/architecture.md)。

各クライテリアは独立した LLM 呼び出しでスコアリングされ、総合スコアは算出しない（クライテリア間の重み付けを前提としない設計）。

## プロジェクト構造

```
src/
├── __init__.py
├── handler.py          # 単一 Lambda エントリポイント、例外階層
├── evaluator.py        # プロンプト構築、LLM 呼び出し、JSON パース、スコア集約
├── criteria.py         # EvaluationCriteria データクラス、S3 ローダー、デフォルト定義
├── config.py           # 環境変数 + Secrets Manager からの Config
├── jobs.py             # クレームチェック（S3 経由の payload 受け渡し）
├── observability.py    # Powertools Tracer / Metrics の共有インスタンス
├── handlers/           # Step Functions の各ステップ
│   ├── prepare.py             # 検証・criteria 解決・ジョブ退避
│   ├── evaluate_criterion.py  # クライテリア 1 件の評価
│   └── summarize.py           # 結果集約・総評生成
└── providers/
    ├── __init__.py     # BaseProvider プロトコル + get_provider() ファクトリ
    ├── anthropic.py    # 同期 Anthropic クライアント
    ├── openai.py       # 同期 OpenAI クライアント
    └── bedrock.py      # Bedrock Converse API（IAM 認証、botocore adaptive retry）

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
├── conftest.py                 # 共有フィクスチャ
├── test_handler.py             # lambda_handler() テスト
├── test_evaluator.py           # プロンプト構築・パース・並列度上限テスト
├── test_criteria.py            # EvaluationCriteria・S3 ローダーテスト
├── test_providers.py           # プロバイダークライアント・botocore 設定テスト
├── test_config.py              # Secrets Manager からの API キー解決テスト
├── test_observability.py       # メトリクス計装テスト
├── test_workflow_handlers.py   # ワークフロー各ステップ + 2 経路の出力一致テスト
└── test_cdk_stack.py           # IaC アサーション + cdk-nag 検査（Docker 不要）

config/
├── parameters.json         # デプロイ・CDK 用パラメータ（リージョン、default_provider、criteria バケット ARN 等）
├── parameters.example.json # テンプレート
└── README.md               # パラメータの説明

cdk/
├── app.py              # CDK App エントリポイント
├── stack.py            # LlmJudgeStack（Lambda×4 + Step Functions + IAM/KMS/S3/SQS/CloudWatch）
└── requirements.txt    # CDK 依存関係

scripts/
├── deploy.sh                  # cdk deploy ラッパー（bootstrap は --bootstrap 時のみ）
└── lambda_pattern_tests.py    # デプロイ済みスタックを複数パターンで検証
                               # （TARGET=lambda|workflow、Bedrock Nova）

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
| `prompt` | `string` | 条件付き | `""` | **プロンプト役**のテキスト。省略可。`prompt` と `response` の両方をトリムした結果が空だとエラー |
| `response` | `string` | 条件付き | `""` | **応答役**のテキスト。省略可。上記と同じく、少なくとも片方はトリム後に非空であること |
| `prompt_descriptor` | `string` | ✗ | `null` | 運用メモ（最大 256 文字、制御文字はタブ・改行のみ可）。ジャッジ向けプロンプトに「Operator note」として挿入される |
| `response_descriptor` | `string` | ✗ | `null` | 応答側の同上 |
| `provider` | `string` | ✗ | `DEFAULT_PROVIDER` 環境変数 | `anthropic` / `openai` / `bedrock` |
| `judge_model` | `string` | ✗ | プロバイダー別デフォルトモデル | ジャッジに使用するモデル ID |
| `criteria_file` | `string` | ✗ | デフォルト balanced クライテリア | S3 URI（例: `s3://bucket/criteria.json`） |
| `system_prompt` | `string` | ✗ | `null` | 評価対象 LLM に与えたシステムプロンプト。ジャッジプロンプトに挿入され、指示追従性の評価に利用される |
| `contexts` | `string` または `string[]` | ✗ | `null` | 評価時に参照する追加コンテキスト（RAG 取得ドキュメント等）。複数指定時は `[1]`, `[2]` 番号付きで挿入される |

**評価モード**: 両方にテキストがあれば従来どおりペア評価。片方だけの場合は、欠けた役はジャッジ向けプロンプト上でプレースホルダに置き換えられ、クライテリアによっては `criterion_assessability` が `not_assessable` になり得る（数値スコアは `criterion_scores` に含めない）。

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
  "criterion_assessability": {
    "accuracy": "assessed",
    "clarity": "assessed",
    "helpfulness": "assessed",
    "completeness": "assessed"
  },
  "reasoning": "総評: 各クライテリアの評価結果は以下のとおりである。accuracy 4.5, clarity 4.0, helpfulness 4.0, completeness 3.5。各観点は独立した意味を持つため総合スコアは算出していない。",
  "judge_model": "claude-sonnet-4-6",
  "provider": "anthropic"
}
```

### フィールド説明

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `criterion_scores` | `object` | クライテリア名 → スコア（1〜5）。**`criterion_assessability` が `assessed` の項目のみ**含む（`not_assessable` はキー自体を省略） |
| `criterion_reasoning` | `object` | クライテリア名 → 推論テキスト。評価不能時も理由を返す |
| `criterion_assessability` | `object` | クライテリア名 → `assessed` または `not_assessable`（各クライテリア必須） |
| `reasoning` | `string` | 全クライテリアをまとめた総評 |
| `judge_model` | `string` | 使用したジャッジモデル名 |
| `provider` | `string` | 使用したプロバイダー（`anthropic` / `openai` / `bedrock`） |

> 総合スコア（`overall_score`）は算出しない。各クライテリアは独立した意味を持つ。

## クライテリアファイル（S3）

S3 上の JSON ファイルでカスタム評価クライテリアを定義できる。

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
| `API_KEYS_SECRET_NAME` | — | Anthropic / OpenAI の API キーを格納した Secrets Manager シークレット名。CDK が設定する |
| `ANTHROPIC_API_KEY` | — | 設定時はシークレットより優先。ローカル開発用 |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | デフォルト Anthropic ジャッジモデル |
| `OPENAI_API_KEY` | — | 設定時はシークレットより優先。ローカル開発用 |
| `OPENAI_MODEL` | `gpt-4o` | デフォルト OpenAI ジャッジモデル |
| `BEDROCK_MODEL` | `jp.anthropic.claude-sonnet-4-6` | デフォルト Bedrock ジャッジモデル（`config/parameters.json` から設定） |
| `REQUEST_TIMEOUT` | `30`（CDK デプロイ時は `60`） | HTTP / Bedrock タイムアウト（秒） |
| `MAX_PARALLEL_CRITERIA` | `5` | 1 回の評価で同時に走るジャッジ呼び出しの上限 |
| `JOBS_BUCKET` | — | ワークフローの payload 退避先バケット。CDK が設定する |
| `LOG_LEVEL` | `INFO` | Powertools ログレベル |
| `POWERTOOLS_SERVICE_NAME` | `llm-judge` | Lambda Powertools サービスタグ |
| `POWERTOOLS_METRICS_NAMESPACE` | `LlmJudge` | EMF メトリクスの名前空間 |

> Bedrock は Lambda 実行ロールの IAM 認証を使用するため、API キー不要。
>
> **API キーは Lambda 環境変数に置かない。** デプロイ後に Secrets Manager へ投入する:
>
> ```bash
> aws secretsmanager put-secret-value --secret-id llm-judge-dev/api-keys \
>   --secret-string '{"ANTHROPIC_API_KEY":"sk-ant-...","OPENAI_API_KEY":""}'
> ```

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
- Docker（`cdk synth` / `cdk deploy` の Lambda アセットバンドルに**必須**。デーモンが起動していること。
  なお `pytest` は Docker なしで全件通る）

### クイックデプロイ

```bash
# 初回のみ（アカウント・リージョン単位の一度きりの操作）
./scripts/deploy.sh --env dev --bootstrap

# 以降のデプロイ
./scripts/deploy.sh --env dev

# リージョン指定
./scripts/deploy.sh --env dev --region ap-northeast-1

# 既存の S3 クライテリアバケットを使う（未指定ならスタックが作成する）
CRITERIA_BUCKET_ARN=arn:aws:s3:::my-bucket ./scripts/deploy.sh --env dev
```

> `bootstrap` は毎回は実行されない。CloudFormation 実行ロールに広い権限を与える
> 一度きりの操作なので、`--bootstrap` を明示したときだけ走る。付与されるポリシーは
> `AdministratorAccess` ではなく、このスタックが作るサービスに絞った集合
> （`CDK_BOOTSTRAP_POLICIES` で上書き可）。

### パラメータファイル

リポジトリ直下の [`config/parameters.json`](config/parameters.json) で `aws_region`・`environment`・`default_provider`・`bedrock_model`・`bedrock_allowed_models`・`bedrock_inference_profile_regions`・`criteria_bucket_arn` を指定する（[`config/README.md`](config/README.md) 参照）。`cdk deploy` の `--context` はスカラーキーを上書きできる。

アカウント ID を含む値は、コミットしない `config/parameters.local.json` に置く。

### 手動 CDK デプロイ

```bash
pip install -r cdk/requirements.txt
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
cdk deploy LlmJudgeStack-dev \
  --app "python3 cdk/app.py" \
  --require-approval never \
  --context environment=dev
```

`cdk synth` / `cdk deploy` は cdk-nag の AWS Solutions ルールパックを通す。未抑制の指摘があれば合成が失敗する。

### デプロイ後の API キー設定

API キーは Lambda 環境変数ではなく Secrets Manager に置く。スタックが空のシークレットを作るので、値を投入する：

```bash
aws secretsmanager put-secret-value \
  --secret-id llm-judge-dev/api-keys \
  --secret-string '{"ANTHROPIC_API_KEY":"sk-ant-...","OPENAI_API_KEY":""}'
```

Bedrock は Lambda 実行ロールの IAM 認証を使うため、この手順は不要。

### 呼び出し

**単一 Lambda 経路**

```bash
aws lambda invoke \
  --function-name llm-judge-dev \
  --payload '{"prompt":"機械学習とは何ですか？","response":"機械学習はAIの一分野です...","provider":"bedrock"}' \
  --cli-binary-format raw-in-base64-out \
  result.json && cat result.json
```

**Step Functions ワークフロー経路**（クライテリア数が多い場合）

```bash
aws stepfunctions start-sync-execution \
  --state-machine-arn <StateMachineArn 出力値> \
  --input '{"prompt":"機械学習とは何ですか？","response":"機械学習はAIの一分野です...","provider":"bedrock"}' \
  --query output --output text
```

どちらも同じイベントを受け付け、同じレスポンスを返す。

## テスト

201 テスト、実際の API 呼び出しなし（`unittest.mock` + `moto[s3]` でモック）。
CDK テンプレートの検証もテスト内でスタックを合成して行うため、**Docker なしで全件実行できる**：

```bash
pytest                                         # 全テスト
pytest tests/test_handler.py -v               # ハンドラーテスト
pytest tests/test_evaluator.py -v             # 評価ロジックテスト
pytest tests/test_criteria.py -v              # クライテリア・S3 テスト
pytest tests/test_providers.py -v             # プロバイダーテスト
pytest tests/test_workflow_handlers.py -v     # ワークフロー + 2 経路の出力一致
pytest tests/test_cdk_stack.py -v             # IaC アサーション + cdk-nag
pytest --cov=src --cov-report=term-missing    # カバレッジ付き
```

## CDK スタックリソース

- **Lambda 関数 ×4**: Python 3.13 / ARM64、512 MB（prepare のみ 256 MB）、300 秒タイムアウト、
  予約同時実行数 10、X-Ray 有効、JSON ログ形式。
  直接呼び出し用 1 つ + ワークフロー用 3 つ（prepare / evaluate-criterion / summarize）
- **Step Functions**: Express ステートマシン（Map の `MaxConcurrency` = 5、
  スロットリング系のリトライは BackoffRate 2 / MaxAttempts 4 / FULL jitter）
- **バンドル**: CDK が公式 Python 3.13 イメージ上で `pip install` と `src/` のコピーを実行（Docker 必須）
- **IAM**: `bedrock:InvokeModel` は `bedrock_allowed_models` で指定したモデルと
  推論プロファイル ARN のみに限定。関数ごとにロールを分離（prepare は Bedrock に到達できず、
  criterion worker は jobs バケットに書き込めない）
- **Secrets Manager**: API キー用シークレット（KMS CMK 暗号化）
- **KMS**: 環境変数・シークレット・DLQ・アラームトピックを暗号化する CMK（自動ローテーション有効）
- **S3**: criteria バケット（暗号化・バージョニング・TLS 必須・アクセスログ）、
  アクセスログバケット、jobs バケット（7 日で失効）
- **SQS**: 非同期呼び出し失敗用 DLQ（KMS 暗号化、14 日保持）
- **CloudWatch**: ロググループ（保持期間 30 日 / prod 90 日）、
  アラーム 5 件（エラー・スロットル・p99 実行時間・DLQ 滞留・ワークフロー失敗）→ SNS、
  ダッシュボード
- **Outputs**: `LambdaFunctionArn`、`LambdaFunctionName`、`StateMachineArn`、
  `CriteriaBucketName`、`JobsBucketName`、`ApiKeysSecretName`、`DeadLetterQueueUrl`、`AlarmTopicArn`
