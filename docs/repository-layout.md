# リポジトリ構成（`src` / `tests` / `scripts` / `cdk` / `contracts`）

サブディレクトリごとの役割。プロダクト概要は [README.md](../README.md)、処理の流れは [architecture.md](architecture.md)。

---

## `src/` — Lambda アプリケーション

| モジュール | 概要 |
|-----------|------|
| `handler.py` | Lambda エントリ、入力検証、例外型、評価の呼び出し |
| `evaluator.py` | クライテリアごとのプロンプト、並列 LLM 呼び出し、パース、総評 |
| `criteria.py` | データモデル、`load_from_s3`、デフォルトクライテリア |
| `config.py` | 環境変数からの設定（コールドスタートでキャッシュ） |
| `providers/` | Anthropic / OpenAI / Bedrock の同期クライアント |

---

## `tests/`

`pytest` で `src/` を検証する。外部ネットワークや実 AWS API には依存しない。

| ファイル | 主な対象 |
|----------|-----------|
| `test_handler.py` | `lambda_handler`、イベント検証、例外マッピング |
| `test_evaluator.py` | プロンプト生成、パース、並列評価まわり |
| `test_criteria.py` | `load_from_dict` / `load_from_s3`（moto）、S3 URI パース |
| `test_providers.py` | 各プロバイダーのモックを使った呼び出しとエラー処理 |
| `conftest.py` | 共有フィクスチャ（あれば） |

実行例は [development.md](development.md) を参照。

---

## `scripts/` — `deploy.sh`

CDK 依存のインストール、`cdk bootstrap`（ベストエフォート）、`LlmJudgeStack` への `cdk deploy` を順に実行する。

| オプション / 変数 | 説明 |
|-------------------|------|
| `--env dev\|prod` | ログ表示用ラベル（既定 `dev`） |
| `--region REGION` | デプロイ先リージョン（`AWS_REGION` より後に評価される） |
| `AWS_REGION` | 未設定時は `config/parameters.json` と `parameters.local.json` をマージした結果の `aws_region`、なければ `us-east-1` |
| `CRITERIA_BUCKET_ARN` | 設定時、`--context criteria_bucket_arn=...` として CDK に渡す |

詳細はスクリプト先頭のコメントと [README.md](../README.md) の「デプロイ」節。

---

## `cdk/` — `LlmJudgeStack`

Python CDK v2 で 1 つの Lambda 関数と IAM を定義する。エントリは [`cdk/app.py`](../cdk/app.py)（`python3 cdk/app.py`）。

### 前提

- **Docker** が必要（アセットバンドル時に公式 Python 3.12 イメージ上で `pip install` と `src/` のコピーを実行）。
- AWS 認証情報が設定済みであること。

### 設定の優先順位（`default_provider` / `criteria_bucket_arn`）

1. CDK の **コンテキスト**で非空の値があればそれを採用（`cdk deploy --context key=value` や [`cdk.json`](../cdk.json) の `context`）。
2. なければ [`config/parameters.json`](../config/parameters.json)（`cdk/app.py` が読み込み、スタックに渡す）。
3. `default_provider` の最終フォールバックは **`bedrock`**。`criteria_bucket_arn` が空なら S3 用 IAM を付けない。

### よく使うコマンド

```bash
pip install -r cdk/requirements.txt   # リポジトリルートから
cdk synth --app "python3 cdk/app.py"
cdk deploy LlmJudgeStack --app "python3 cdk/app.py" --require-approval never
```

リージョンは `AWS_REGION` または `config/parameters.json` の `aws_region`（`scripts/deploy.sh` 利用時）。

### スタックの出力

- `LambdaFunctionArn` — 関数 ARN（エクスポート名 `LlmJudgeFunctionArn`）
- `LambdaFunctionName` — 関数名

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
