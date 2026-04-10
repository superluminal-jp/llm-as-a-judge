# デプロイ・CDK パラメータ

`parameters.json` で AWS リージョンや Lambda のデフォルトプロバイダー、クライテリア用 S3 バケットをまとめて指定する。

## ファイル

| ファイル | 説明 |
|----------|------|
| `parameters.json` | チーム／環境用の実設定（リポジトリにコミットするかは方針に従う） |
| `parameters.example.json` | テンプレート。新規環境ではコピーして編集する |
| `parameters.local.json` | （任意）`parameters.json` の上書き。[`cdk/app.py`](../cdk/app.py) が両方をマージして読み込む。[`.gitignore`](../.gitignore) で無視する想定 |

## キー

| キー | 型 | 説明 |
|------|-----|------|
| `aws_region` | string | デプロイ先リージョン。`scripts/deploy.sh` が `AWS_REGION` 未指定時に利用 |
| `environment` | string | ラベル用（例: `dev` / `prod`）。デプロイログに表示されるだけ |
| `default_provider` | string | Lambda の `DEFAULT_PROVIDER`（イベントで未指定時）。`anthropic` / `openai` / `bedrock` |
| `criteria_bucket_arn` | string | クライテリア JSON 用バケットの **ARN**（例: `arn:aws:s3:::my-bucket`）。空なら S3 読み取り IAM を付与しない |

## 優先順位（`default_provider` / `criteria_bucket_arn`）

| 優先度 | ソース |
|--------|--------|
| 1 | CDK コンテキストの **非空** の値（`cdk deploy --context key=value` など） |
| 2 | `parameters.json` を [`cdk/app.py`](../cdk/app.py) が読み込んでスタックに渡した値 |
| 3 | コード上の既定（`default_provider` → `bedrock`、`criteria_bucket_arn` → 空） |

`aws_region` は CDK スタックのプロパティではなく、主に **`scripts/deploy.sh`** と開発者の `AWS_REGION` で解釈される。

## セキュリティ

シークレット（API キー、トークン）は **ここに書かない**。デプロイ後に Lambda 環境変数、Systems Manager Parameter Store、または Secrets Manager で設定する。

関連: [docs/repository-layout.md](../docs/repository-layout.md)（CDK・デプロイ）、[docs/troubleshooting.md](../docs/troubleshooting.md)。
