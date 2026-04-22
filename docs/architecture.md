# アーキテクチャ

## 目的

評価対象 LLM の **プロンプト** と **回答** を入力とし、別の LLM（ジャッジ）が **クライテリアごと** にスコアと根拠を返す。クライテリア間の重み付けや単一の総合スコアは設計上持たない。

## リクエストの流れ

1. **`handler.lambda_handler`** がイベントを検証し、`provider`・`judge_model`・`criteria_file`（S3 URI）・`system_prompt`・`contexts` を解釈する。
2. **クライテリア**は `criteria_file`（S3 URI）があれば **`load_from_s3`**、なければ **`DefaultCriteria.balanced()`**（組み込み 4 軸: accuracy, clarity, helpfulness, completeness）。
3. **`get_provider`** が Anthropic / OpenAI / Bedrock のいずれかを返す（環境変数で API キーやモデル既定を解決）。
4. **`evaluator.evaluate`** が各クライテリアを **スレッドプールで並列** に評価し、必要なら最後に **総評（`reasoning`）** 用の追加 LLM 呼び出しを行う。
5. 成功時は **dict** を返す。エラー時は **例外**（`ValidationError` 等）を送出し、Lambda ランタイムが失敗として扱う（`{"error": ...}` 形式の成功レスポンスは使わない）。

## モジュールの役割

| モジュール | 役割 |
|-----------|------|
| `handler` | 入力検証、例外型の定義、ロギング、オーケストレーション |
| `criteria` | `EvaluationCriteria` / `CriterionDefinition`、S3 からの JSON 読み込み、`load_from_dict` |
| `config` | 環境変数からの `Config`（コールドスタートでキャッシュ） |
| `providers` | `BaseProvider`、各クラウド SDK の同期呼び出し |
| `evaluator` | ジャッジ用プロンプト組み立て、並列 `complete`、JSON パース、総評生成 |

## 並列性とコスト

- クライテリア **N 個** なら、評価フェーズでは最大 **N 回** のジャッジ LLM 呼び出し（並列）。
- 総評が有効な場合は **さらに 1 回** の呼び出しが追加される（実装は `evaluator` を参照）。

## 観測性

- AWS Lambda Powertools の `Logger` を使用（`POWERTOOLS_SERVICE_NAME` 等）。
- 処理時間が閾値を超えた場合に INFO ログを出す箇所あり（handler / evaluator）。
