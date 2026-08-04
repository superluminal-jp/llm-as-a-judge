# リポジトリ構成（`src` / `tests` / `scripts` / `cdk` / `contracts`）

サブディレクトリごとの役割。プロダクト概要は [README.md](../README.md)、処理の流れは [architecture.md](architecture.md)。

---

## `src/` — Lambda アプリケーション

| モジュール | 概要 |
|-----------|------|
| `handler.py` | 単一 Lambda 経路のエントリ、入力検証、例外型、評価の呼び出し |
| `evaluator.py` | クライテリアごとのプロンプト、並列 LLM 呼び出し、パース、総評 |
| `criteria.py` | データモデル、`load_from_s3`、デフォルトクライテリア |
| `config.py` | 環境変数と Secrets Manager からの設定（コールドスタートでキャッシュ） |
| `jobs.py` | クレームチェック。Step Functions の 256KB 制限を避けるため payload を S3 経由で渡す |
| `observability.py` | Powertools `Tracer` / `Metrics` の共有インスタンスとメトリクス名 |
| `handlers/` | Step Functions の各ステップ（`prepare` / `evaluate_criterion` / `summarize`） |
| `providers/` | Anthropic / OpenAI / Bedrock の同期クライアント |

`handlers/` の 3 ステップはプロンプト構築・パース・集約を自前で持たず、
すべて `evaluator.py` の関数を再利用する。そのため単一 Lambda 経路と
ワークフロー経路の出力は一致する（`tests/test_workflow_handlers.py` で検証）。

---

## `tests/`

`pytest` で `src/` を検証する。外部ネットワークや実 AWS API には依存しない。

| ファイル | 主な対象 |
|----------|-----------|
| `test_handler.py` | `lambda_handler`、イベント検証、例外マッピング |
| `test_evaluator.py` | プロンプト生成、パース、並列評価まわり |
| `test_criteria.py` | `load_from_dict` / `load_from_s3`（moto）、S3 URI パース |
| `test_providers.py` | 各プロバイダーのモックを使った呼び出し、botocore クライアント設定、エラー処理 |
| `test_config.py` | 環境変数と Secrets Manager からの API キー解決 |
| `test_observability.py` | メトリクス計装（計装の失敗が評価を落とさないこと含む） |
| `test_workflow_handlers.py` | ワークフロー各ステップ、クレームチェック、2 経路の出力一致 |
| `test_cdk_stack.py` | 合成した CloudFormation への IaC アサーションと cdk-nag 検査（Docker 不要） |
| `conftest.py` | 共有フィクスチャ（あれば） |

実行例は [development.md](development.md) を参照。

---

## `scripts/` — `deploy.sh`

CDK 依存のインストールと `LlmJudgeStack-<env>` への `cdk deploy` を実行する。
`cdk bootstrap` は **`--bootstrap` を明示したときだけ**走る（アカウント・リージョン単位で
広い権限のロールを作る一度きりの操作のため）。

| オプション / 変数 | 説明 |
|-------------------|------|
| `--env dev\|prod` | 環境名。**スタック名 `LlmJudgeStack-<env>`** とリソース名を決める（既定 `dev`） |
| `--region REGION` | デプロイ先リージョン（`AWS_REGION` より後に評価される） |
| `--bootstrap` | `cdk bootstrap` を実行する。初回のみ |
| `AWS_REGION` | 未設定時は `config/parameters.json` と `parameters.local.json` をマージした結果の `aws_region`、なければ `ap-northeast-1` |
| `CRITERIA_BUCKET_ARN` | 設定時、`--context criteria_bucket_arn=...` として CDK に渡す。未設定ならスタックがバケットを作成する |
| `CDK_BOOTSTRAP_POLICIES` | bootstrap 時の CloudFormation 実行ロールに付けるマネージドポリシー ARN（カンマ区切り）。既定はこのスタックが作るサービスに絞った集合で、`AdministratorAccess` ではない |

詳細はスクリプト先頭のコメントと [README.md](../README.md) の「デプロイ」節。

---

## `cdk/` — `LlmJudgeStack-<env>`

Python CDK v2 で Lambda 4 関数、Step Functions ワークフロー、および付随する
IAM / KMS / S3 / SQS / CloudWatch リソースを定義する。エントリは
[`cdk/app.py`](../cdk/app.py)（`python3 cdk/app.py`）。リソース一覧は
[README.md](../README.md) の「CDK スタックリソース」節。

### 前提

- **Docker** が必要（アセットバンドル時に公式 Python 3.13 イメージ上で `pip install` と `src/` のコピーを実行）。
  ただし `pytest tests/test_cdk_stack.py` はバンドルを省略して合成するため Docker なしで通る。
- AWS 認証情報が設定済みであること。
- `cdk synth` は cdk-nag の AWS Solutions ルールパックを通る。未抑制の指摘があれば失敗する。

### 設定の優先順位

1. CDK の **コンテキスト**で非空の値があればそれを採用（`cdk deploy --context key=value` や [`cdk.json`](../cdk.json) の `context`）。
   対象は `environment` / `aws_region` / `default_provider` / `bedrock_model` / `criteria_bucket_arn`。
2. なければ [`config/parameters.local.json`](../config/README.md)（gitignore 済み）。
3. なければ [`config/parameters.json`](../config/parameters.json)。
4. 最終フォールバックはコード上の既定（`default_provider` → `bedrock`、`environment` → `dev` など）。

リスト型のキー（`bedrock_allowed_models` / `bedrock_inference_profile_regions`）は
パラメータファイルでのみ指定する。

### よく使うコマンド

```bash
pip install -r cdk/requirements.txt   # リポジトリルートから
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
cdk synth --app "python3 cdk/app.py" --context environment=dev
cdk deploy LlmJudgeStack-dev --app "python3 cdk/app.py" --require-approval never --context environment=dev
```

リージョンは `AWS_REGION` または `config/parameters.json` の `aws_region`（`scripts/deploy.sh` 利用時）。

### スタックの出力

- `LambdaFunctionArn` / `LambdaFunctionName` — 単一 Lambda 経路の関数
- `StateMachineArn` — ワークフロー経路のステートマシン（`start-sync-execution` で呼ぶ）
- `CriteriaBucketName` — クライテリア JSON 置き場
- `JobsBucketName` — ワークフローの payload 退避先
- `ApiKeysSecretName` — Anthropic / OpenAI の API キーを入れるシークレット
- `DeadLetterQueueUrl` — 非同期呼び出し失敗の退避先
- `AlarmTopicArn` — アラーム通知先 SNS トピック

実装の詳細は [`cdk/stack.py`](../cdk/stack.py) の docstring を参照。

---

## `contracts/` — JSON Schema

Lambda の入出力と S3 クライテリアファイルの **機械可読な形**。実装の正は `src/` とテスト。ファイル単位のパスは [schemas.md](schemas.md) を参照。

| ファイル | 説明 |
|----------|------|
| [`lambda-event.json`](../contracts/lambda-event.json) | 呼び出しイベント（`contexts` は `src/handler.py` と一致） |
| [`lambda-response.json`](../contracts/lambda-response.json) | 成功時のレスポンス |
| [`criteria-file.json`](../contracts/criteria-file.json) | S3 に置くクライテリア JSON |

長文仕様は **`specs/`** に置く想定だが Git 管理外（[`.gitignore`](../.gitignore)）。
