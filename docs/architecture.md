# アーキテクチャ

## 目的

評価対象 LLM の **プロンプト** と **回答** を入力とし、別の LLM（ジャッジ）が **クライテリアごと** にスコアと根拠を返す。クライテリア間の重み付けや単一の総合スコアは設計上持たない。

## 2 つの実行経路

同じイベントを受け付け、**同じレスポンス**（[`contracts/lambda-response.json`](../contracts/lambda-response.json)）を返す経路が 2 つある。

| 経路 | 起動方法 | 並列実行の担い手 | 向いている場面 |
|------|----------|------------------|----------------|
| **単一 Lambda** | `aws lambda invoke` | Lambda 内スレッドプール（上限 `MAX_PARALLEL_CRITERIA`） | クライテリア数が少ない。構成要素が 1 つで済む |
| **Step Functions ワークフロー** | `aws stepfunctions start-sync-execution` | Map ステート（`MaxConcurrency`） | クライテリア数が多い。リトライ・失敗箇所の可視化が要る |

両者の出力が一致することは `tests/test_workflow_handlers.py::TestWorkflowMatchesDirectInvoke` が検証している。

### 経路 1: 単一 Lambda

```
Lambda イベント（`prompt` / `response` は少なくとも一方必須、[provider]、[criteria_file]、任意 descriptor）
    └─→ handler.lambda_handler
        ├─→ criteria.load_from_s3()   または   DefaultCriteria.balanced()
        ├─→ providers.get_provider()  → AnthropicProvider / OpenAIProvider / BedrockProvider
        └─→ evaluator.evaluate()
              ├─→ ThreadPoolExecutor(min(クライテリア数, MAX_PARALLEL_CRITERIA))
              ├─→ build_evaluation_prompt_single_criterion() → provider.complete()
              └─→ parse_single_criterion_response()
                  └─→ { criterion_scores, criterion_reasoning, criterion_assessability, reasoning, judge_model, provider }
```

### 経路 2: Step Functions（Express・同期実行）

```
StartSyncExecution
  └─→ Prepare            (Lambda: src.handlers.prepare)
  │     入力検証 → criteria 解決 → ジョブ payload を S3 に退避 → { job_uri, items[] }
  └─→ EvaluateCriteria   (Map: MaxConcurrency = MAX_PARALLEL_CRITERIA)
  │     └─→ EvaluateCriterion (Lambda: src.handlers.evaluate_criterion)
  │           job_uri から payload 取得 → クライテリア 1 件のみ評価
  └─→ Summarize          (Lambda: src.handlers.summarize)
        全結果を元の順序に戻す → 総評生成 → 最終レスポンス組み立て
```

**クレームチェック**: Step Functions のステート間データ上限は 256 KB。`prompt` / `response` / `contexts` は容易に超えるため、Prepare が payload を S3（jobs バケット）に書き、ステート間は `s3://` URI だけが流れる（[`src/jobs.py`](../src/jobs.py)）。ジョブオブジェクトはライフサイクルルールで失効する。

**リトライ**: スロットリング系エラーのリトライは Map ステート側（`BackoffRate: 2`、`MaxAttempts: 4`、FULL jitter）が担う。Lambda 内で `time.sleep` しないため、バックオフ中の課金時間が発生しない。

**Express の制約**: 同期実行の上限は 5 分。クライテリア数 × 1 件あたりの応答時間がこれを超える規模では Standard ワークフロー（非同期）への変更が必要になる。

## モジュールの役割

| モジュール | 役割 |
|-----------|------|
| `handler` | 入力検証、例外型の定義、ロギング、単一 Lambda 経路のオーケストレーション |
| `handlers/prepare` | ワークフローの検証・criteria 解決・ジョブ退避 |
| `handlers/evaluate_criterion` | ワークフローの 1 クライテリア評価 |
| `handlers/summarize` | ワークフローの結果集約・総評生成 |
| `criteria` | `EvaluationCriteria` / `CriterionDefinition`、S3 からの JSON 読み込み、`load_from_dict` |
| `jobs` | クレームチェック用のジョブ payload 書き込み・読み出し（コンテナ内キャッシュ付き） |
| `config` | 環境変数からの `Config`（コールドスタートでキャッシュ）、Secrets Manager からの API キー解決 |
| `providers` | `BaseProvider`、各クラウド SDK の同期呼び出し |
| `evaluator` | ジャッジ用プロンプト組み立て、並列 `complete`、JSON パース、総評生成 |
| `observability` | Powertools `Tracer` / `Metrics` の共有インスタンスとメトリクス名 |

プロンプト構築・レスポンスパース・結果集約は **`evaluator` の関数が唯一の実装**であり、2 経路が共有する。

## 並列性とコスト

- クライテリア **N 個** なら、評価フェーズで **N 回** のジャッジ LLM 呼び出し。総評でさらに **1 回**。
- 同時実行数は `MAX_PARALLEL_CRITERIA`（既定 5）で頭打ちになる。N がこれを超える場合は複数波に分かれる。
- Lambda の予約同時実行数（既定 10）が、サービス全体から Bedrock への同時呼び出し数の上限を決める。
- Bedrock クライアントの `max_pool_connections` は `MAX_PARALLEL_CRITERIA` から算出される。

## 認証とシークレット

- **Bedrock**: Lambda 実行ロールの IAM 認証。API キー不要。
- **Anthropic / OpenAI**: Secrets Manager のシークレット（`API_KEYS_SECRET_NAME`）から遅延取得し、Powertools が既定 300 秒キャッシュする。環境変数に平文で置かない。
- クロスリージョン推論プロファイル（`jp.` 等のプレフィックス付き ID）は、プロファイル ARN とルーティング先各リージョンの基盤モデル ARN の**両方**に `bedrock:InvokeModel` が要る。詳細は [`config/README.md`](../config/README.md)。

## 観測性

- **ログ**: Powertools `Logger`（JSON 構造化、`correlation_id` にリクエスト ID）。ロググループは CDK が明示作成し保持期間を設定する。
- **トレース**: X-Ray 有効。Powertools `Tracer` がハンドラーと `_evaluate_one_criterion` を計装する。レスポンス本文はトレースに含めない（提出物と講評を含むため）。
- **メトリクス**: CloudWatch EMF。`EvaluationsCompleted` / `EvaluationsFailed` / `CriterionEvaluationFailed` / `NotAssessableCount` / `BedrockThrottled` / `JudgeLatencyMs`。ディメンションは `provider` と `judge_model`。
- **アラーム**: Lambda エラー・スロットル・p99 実行時間・DLQ 滞留・ワークフロー失敗を SNS に通知。
- 計装の失敗が評価を落とすことはない（`src/observability.py` の `add_count` / `add_latency_ms` は例外を握る）。

## エラー処理の方針

クライテリア 1 件でも評価できなければ **評価全体を失敗**させる。スコアを付けられなかったクライテリアと、ジャッジが「評価不能（`not_assessable`）」と判断したクライテリアは意味が違うため、前者を後者に丸めるとレスポンスは完全に見えるのに実際はルーブリックを満たしていない、という状態になる。失敗は `CriterionEvaluationFailed` メトリクスとログで可視化する。
