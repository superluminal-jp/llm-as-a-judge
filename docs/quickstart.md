# クイックスタート

ローカルでテストを通し、AWS Lambda にデプロイして 1 回呼び出すまでの最短ガイド。

- **所要時間**: 約 15 分（初回 CDK bootstrap 込み）
- **対象 OS**: macOS / Linux（Windows は WSL2 推奨）
- **ゴール**: ローカルテストが緑になり、デプロイした Lambda から評価結果 JSON が返ること

> 急ぎの場合は、まず [ステップ 1](#1-ローカルセットアップ3-分) と [ステップ 2](#2-ローカルでテストを実行1-分) だけでもコードの健全性を確認できる。AWS 環境がなくても進められる。

---

## 前提条件

| 必要なもの | 確認コマンド | 備考 |
|------------|--------------|------|
| Python 3.12 | `python3 --version` | 3.12.x 系を想定 |
| AWS CLI（認証済み） | `aws sts get-caller-identity` | デプロイに必要 |
| Docker（起動中） | `docker info` | CDK が Lambda アセットをコンテナでバンドル |
| Node.js + AWS CDK | `cdk --version` | 未導入なら `npm install -g aws-cdk` |

すべて揃っていなくてもステップ 1〜2 までは進められる。AWS まわりはステップ 3 の直前でも構わない。

---

## 1. ローカルセットアップ（3 分）

```bash
git clone <repository-url> llm-as-a-judge
cd llm-as-a-judge

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt -r requirements-dev.txt
```

> 失敗時は [troubleshooting.md](troubleshooting.md) を参照。

---

## 2. ローカルでテストを実行（1 分）

```bash
pytest -q
```

**期待出力**: 全テスト（94 件前後）が `passed` で終わる。ここまで通れば、ランタイムコードはローカルで検証済み。AWS 課金は一切発生しない（実 API 呼び出しは `unittest.mock` と `moto[s3]` でモック）。

---

## 3. デプロイパラメータの最小設定（1 分）

[`config/parameters.json`](../config/parameters.json) を開き、**`aws_region`** をデプロイ先に合わせる。

```json
{
  "aws_region": "ap-northeast-1",
  "environment": "dev",
  "default_provider": "bedrock",
  "criteria_bucket_arn": ""
}
```

ポイント:

- **シークレット（API キー）は JSON に書かない**。デプロイ後に Lambda 環境変数で設定する。
- カスタムクライテリアを S3 から読みたい場合のみ `criteria_bucket_arn` を埋める（後からでも可）。
- チーム共通設定を汚さずローカルで上書きしたい場合は `config/parameters.local.json` を作成（[詳細](../config/README.md)）。

---

## 4. デプロイ（初回 5〜10 分、2 回目以降 1〜2 分）

```bash
./scripts/deploy.sh
```

リージョンを引数で上書きしたい場合:

```bash
./scripts/deploy.sh --region ap-northeast-1
```

**期待出力**: 末尾に Lambda の ARN が表示される。

```
============================================
  Deployment complete!
  Lambda ARN: arn:aws:lambda:ap-northeast-1:123456789012:function:LlmJudgeStack-...
  Region:     ap-northeast-1
  Env:        dev
============================================
```

> 初回は CDK bootstrap が走るため時間がかかる。Docker が起動していないと失敗するので注意。

ARN から **関数名** を控えておく（最後の `:` 以降、例: `LlmJudgeStack-LlmJudgeFunction...`）。次のステップで使う。

---

## 5. （任意）API キーの設定

**Bedrock のみ**で評価する場合は不要（Lambda 実行ロールの IAM 認証で動く）。

Anthropic / OpenAI を使う場合のみ:

```bash
aws lambda update-function-configuration \
  --function-name <関数名> \
  --region <リージョン> \
  --environment "Variables={ANTHROPIC_API_KEY=sk-ant-...,DEFAULT_PROVIDER=anthropic}"
```

---

## 6. 初回呼び出し（30 秒）

組み込みの **Balanced クライテリア（4 軸）** で評価する最小ペイロード:

```bash
aws lambda invoke \
  --function-name <関数名> \
  --region <リージョン> \
  --cli-binary-format raw-in-base64-out \
  --payload '{"prompt":"1+1は？","response":"2です。","provider":"bedrock"}' \
  result.json && cat result.json
```

**期待レスポンス**（`result.json`）の概形:

```json
{
  "criterion_scores": { "accuracy": 5.0, "clarity": 5.0, "helpfulness": 4.0, "completeness": 3.5 },
  "criterion_reasoning": { "accuracy": "...", "clarity": "...", "...": "..." },
  "reasoning": "総評: ...",
  "judge_model": "anthropic.claude-sonnet-4-6",
  "provider": "bedrock"
}
```

これでセットアップは完了。`result.json` は [`.gitignore`](../.gitignore) 対象なのでコミットされない。

---

## よくあるつまずき

| 症状 | 対処 |
|------|------|
| `aws sts get-caller-identity` が失敗 | `aws configure` で認証情報を設定、または `AWS_PROFILE` を確認 |
| `cdk synth` / `deploy` が Docker エラー | Docker Desktop / `dockerd` を起動 |
| `AccessDeniedException`（Bedrock） | リージョンでモデルが有効化されているか、クロスリージョン推論プロファイルが必要か確認 |
| `CriteriaLoadError` | S3 URI 形式 `s3://bucket/key` と `s3:GetObject` 権限を確認 |

詳しくは [troubleshooting.md](troubleshooting.md) 参照。

---

## 次に読むもの

| ドキュメント | 用途 |
|--------------|------|
| [README.md](../README.md) | イベント全フィールド、環境変数、エラー種別の一次情報 |
| [architecture.md](architecture.md) | 内部の処理フローとモジュール構成 |
| [development.md](development.md) | テスト・開発ループ・カバレッジ |
| [schemas.md](schemas.md) | Lambda イベント／クライテリア JSON Schema |
| [criteria/README.md](../criteria/README.md) | カスタムクライテリアの作り方（S3） |
