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

シークレット（Anthropic / OpenAI の API キー）は **JSON には書かない**。デプロイ後に Secrets Manager へ投入する（下記）。アカウント ID を含む値も `parameters.local.json` に置く。

---

## 3. デプロイ

```bash
# 初回のみ（アカウント・リージョン単位で一度きり）
./scripts/deploy.sh --env dev --bootstrap

# 以降
./scripts/deploy.sh --env dev
# またはリージョン指定
./scripts/deploy.sh --env dev --region ap-northeast-1
```

スタック名は `LlmJudgeStack-<env>`。完了後、Lambda ARN・関数名・criteria バケット名・シークレット名などが出力される。

---

## 4. API キー（Anthropic / OpenAI を使う場合）

Bedrock のみなら Lambda 実行ロールの IAM 認証で足りるので、この手順は不要。

Anthropic / OpenAI を使う場合は、スタックが作成した Secrets Manager シークレットに値を入れる。**Lambda の環境変数には入れない**:

```bash
aws secretsmanager put-secret-value \
  --secret-id llm-judge-dev/api-keys \
  --region <リージョン> \
  --secret-string '{"ANTHROPIC_API_KEY":"sk-ant-...","OPENAI_API_KEY":""}'
```

キーは呼び出し時に遅延取得され、コンテナ内に既定 300 秒キャッシュされる。

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

クライテリア数が多い場合は **Step Functions ワークフロー**でも同じイベントを実行できる（同じレスポンスが返る）:

```bash
aws stepfunctions start-sync-execution \
  --state-machine-arn <StateMachineArn 出力値> \
  --region <リージョン> \
  --input '{"prompt":"1+1は？","response":"2です。","provider":"bedrock"}' \
  --query output --output text
```

デプロイ後に **複数パターンをまとめて試す**場合は、リポジトリルートで `python3 scripts/lambda_pattern_tests.py`（スタック出力を自動参照、`judge_model` は `amazon.nova-lite-v1:0` 固定）。`TARGET=workflow` を付けると同じケースをワークフロー経路で実行する。

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
