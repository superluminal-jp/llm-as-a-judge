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
| `aws_region` | string | デプロイ先リージョン。CDK スタックの `env` に渡され、Bedrock IAM のリージョン限定 ARN 生成にも使われる |
| `environment` | string | 環境名（例: `dev` / `prod`）。**スタック名 `LlmJudgeStack-<environment>`**、リソース名、ロググループ保持期間、削除ポリシーを決める |
| `default_provider` | string | Lambda の `DEFAULT_PROVIDER`（イベントで未指定時）。`anthropic` / `openai` / `bedrock` |
| `bedrock_model` | string | Bedrock の既定ジャッジモデル ID。`jp.` などのリージョンプレフィックス付きはクロスリージョン推論プロファイル ID として扱われる |
| `bedrock_allowed_models` | string[] | Lambda が呼び出しを許可される Bedrock モデル／推論プロファイル ID の**全リスト**。IAM ポリシーはこのリストからのみ生成される（`bedrock_model` は自動で含まれる） |
| `bedrock_inference_profile_regions` | string[] | クロスリージョン推論プロファイルのルーティング先リージョン。各リージョンの基盤モデル ARN に対して `bedrock:InvokeModel` が付与される |
| `criteria_bucket_arn` | string | **既存**のクライテリア用バケット ARN（例: `arn:aws:s3:::my-bucket`）。**空ならスタックがバケットを新規作成**し、`criteria/*.json` を配置する |

### Bedrock IAM と推論プロファイル

`jp.anthropic.claude-sonnet-4-6` のようなリージョンプレフィックス付き ID は
**基盤モデル ID ではなく推論プロファイル ID** である。これを呼び出すには次の両方が必要になる。

1. 呼び出し元リージョンの推論プロファイル ARN
   （`arn:aws:bedrock:<region>:<account>:inference-profile/<profile-id>`）に対する `bedrock:InvokeModel`
2. プロファイルがルーティングする**各リージョン**の基盤モデル ARN
   （`arn:aws:bedrock:<routed-region>::foundation-model/<base-model-id>`）に対する `bedrock:InvokeModel`

2 だけを付与すると `AccessDeniedException` になる。
`bedrock_allowed_models` と `bedrock_inference_profile_regions` から
[`cdk/stack.py`](../cdk/stack.py) の `_bedrock_model_resources()` が両方を生成する。

## 優先順位

| 優先度 | ソース |
|--------|--------|
| 1 | CDK コンテキストの **非空** の値（`cdk deploy --context key=value` など） |
| 2 | `parameters.local.json`（gitignore 済み。`parameters.json` を上書き） |
| 3 | `parameters.json` を [`cdk/app.py`](../cdk/app.py) が読み込んでスタックに渡した値 |
| 4 | コード上の既定（`default_provider` → `bedrock`、`environment` → `dev` など） |

コンテキストで上書きできるのは `environment` / `aws_region` / `default_provider` /
`bedrock_model` / `criteria_bucket_arn` の各スカラーキー。リスト型の 2 キーは
パラメータファイルでのみ指定する。

## セキュリティ

- シークレット（API キー、トークン）は **ここに書かない**。
  Anthropic / OpenAI の API キーはスタックが作成する **Secrets Manager シークレット**
  （`llm-judge-<environment>/api-keys`）に格納する。Lambda 環境変数には入らない。

  ```bash
  aws secretsmanager put-secret-value \
    --secret-id llm-judge-dev/api-keys \
    --secret-string '{"ANTHROPIC_API_KEY":"sk-ant-...","OPENAI_API_KEY":""}'
  ```

  Bedrock は Lambda 実行ロールの IAM 認証を使うためキー不要。

- **AWS アカウント ID を含む値（バケット ARN など）はコミットしない。**
  `parameters.local.json` に置く（[`.gitignore`](../.gitignore) 済み）。

関連: [docs/repository-layout.md](../docs/repository-layout.md)（CDK・デプロイ）、[docs/troubleshooting.md](../docs/troubleshooting.md)。
