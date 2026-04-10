# Quickstart

最短で **テストを通し**、**1 回 Lambda をデプロイして呼び出す**までの手順。前提は macOS / Linux と Python 3.12 系を想定する。

---

## 1. リポジトリと依存関係

```bash
git clone <repository-url> llm-as-a-judge
cd llm-as-a-judge

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

ここまでで **94 件前後のテストがすべて成功**すれば、ランタイムコードはローカル検証済み。

---

## 2. AWS とパラメータ（デプロイ前）

1. **AWS CLI** が使え、`aws sts get-caller-identity` が通ること。
2. **Docker** が起動していること（CDK が Lambda アセットをバンドルするため必須）。
3. [`config/parameters.json`](../config/parameters.json) を開き、少なくとも **`aws_region`** をデプロイ先に合わせる。  
   S3 上のクライテリアを読ませる場合は **`criteria_bucket_arn`** にバケット ARN（例: `arn:aws:s3:::my-bucket`）を入れる。  
   チーム用の上書きだけローカルに置きたい場合は [`config/parameters.local.json`](../config/README.md)（[`cdk/app.py`](../cdk/app.py) が `parameters.json` とマージ）。

シークレット（Anthropic / OpenAI の API キー）は **JSON には書かない**。デプロイ後に Lambda の環境変数で設定する（下記）。

---

## 3. デプロイ

```bash
./scripts/deploy.sh
# またはリージョン指定
./scripts/deploy.sh --region ap-northeast-1
```

初回は CDK の bootstrap が走る場合がある。完了後、スタック出力に **Lambda ARN** が表示される。

---

## 4. API キー（Anthropic / OpenAI を使う場合）

Bedrock のみなら Lambda 実行ロールの IAM で足りることが多い。Anthropic / OpenAI をデフォルトまたはイベントで使う場合は、例として:

```bash
aws lambda update-function-configuration \
  --function-name <LlmJudgeStack が出力した関数名> \
  --region <リージョン> \
  --environment "Variables={ANTHROPIC_API_KEY=sk-ant-...,DEFAULT_PROVIDER=anthropic}"
```

---

## 5. 初回呼び出し（最小ペイロード）

`criteria_file` を省略すると、組み込みの **Balanced（4 軸）** クライテリアが使われる。

```bash
aws lambda invoke \
  --function-name <関数名> \
  --region <リージョン> \
  --cli-binary-format raw-in-base64-out \
  --payload '{"prompt":"1+1は？","response":"2です。","provider":"bedrock"}' \
  result.json && cat result.json
```

`result.json` は [`.gitignore`](../.gitignore) 対象。成功時は `criterion_scores`・`criterion_reasoning`・`reasoning` などが返る。

---

## 6. カスタムクライテリア（S3）

1. `criteria/default.json` などを **S3 にアップロード**する。  
2. Lambda イベントに **`criteria_file": "s3://バケット名/キー"`** を付ける。  
3. デプロイ時に **`criteria_bucket_arn`** を付けているか、またはロールに `s3:GetObject` があること。

詳細は [README.md](../README.md) の「クライテリアファイル（S3）」と [criteria/README.md](../criteria/README.md)。

---

## 次のステップ

| 読むもの | 内容 |
|----------|------|
| [README.md](../README.md) | イベント全フィールド、環境変数、エラー種別 |
| [architecture.md](architecture.md) | 内部の処理の流れ |
| [troubleshooting.md](troubleshooting.md) | 失敗時の切り分け |
| [development.md](development.md) | テスト・開発ループ |
