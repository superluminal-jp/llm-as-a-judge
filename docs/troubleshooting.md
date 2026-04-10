# トラブルシューティング

## CDK・ビルド

| 現象 | 確認すること |
|------|----------------|
| `cdk synth` / `deploy` が Docker 関連で失敗 | Docker デーモンが起動しているか。Lambda のアセットはコンテナ内で `pip install` している。 |
| バンドル後に `ModuleNotFoundError` | `requirements.txt` に依存が揃っているか。`src/` がバンドルに含まれているか（`cdk/stack.py` の `cp -r src`）。 |

## IAM・Bedrock

| 現象 | 確認すること |
|------|----------------|
| `AccessDeniedException` / スロットリング | リージョンと **クロスリージョン推論プロファイル**の要否（Claude 系）。`BedrockProvider` のリトライログ。 |
| モデル ID が無効 | そのリージョンで利用可能なモデル ID か。環境変数 `BEDROCK_MODEL` とイベントの `judge_model`。 |

## S3 クライテリア

| 現象 | 確認すること |
|------|----------------|
| `CriteriaLoadError`（オブジェクトなし） | バケット・キー・URI 形式 `s3://bucket/key`。Lambda ロールに `s3:GetObject` があるか。 |
| `CriteriaLoadError`（JSON 不正） | `criteria-file` 契約に合うか（[schemas.md](schemas.md)）。 |

## プロバイダー（Anthropic / OpenAI）

| 現象 | 確認すること |
|------|----------------|
| `ConfigurationError`（API キー） | Lambda 環境変数 `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` が設定されているか。 |
| タイムアウト | `REQUEST_TIMEOUT`、および API 側のレート制限。 |

## イベント形式

| 現象 | 確認すること |
|------|----------------|
| `ValidationError` | 必須フィールド `prompt` / `response`。`contexts` は文字列または文字列のリスト。 |
