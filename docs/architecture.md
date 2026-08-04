# アーキテクチャ

## 目的

評価対象 LLM の **プロンプト** と **回答** を入力とし、別の LLM（ジャッジ）が **クライテリアごと** にスコアと根拠を返す。クライテリア間の重み付けや単一の総合スコアは設計上持たない。

## 実行モデル

評価は **Step Functions ワークフロー**として実行される。以前は 1 つの Lambda がスレッドプールでクライテリアを並列処理していたが、その経路は廃止した。同時実行数・リトライ・失敗箇所の特定がアプリコードではなくサービス側の責務になり、1 invocation に収まらない規模まで伸ばせる。

```
Prepare → Map(MaxConcurrency)[EvaluateCriterion] → Summarize
```

| ステート | Lambda | 役割 |
|---------|--------|------|
| Prepare | `src.handlers.prepare` | 入力検証、criteria 解決、ジョブ payload の S3 退避、content hash 算出 |
| EvaluateCriterion | `src.handlers.evaluate_criterion` | クライテリア **1 件**の評価。結果を S3 に書き、ポインタを返す |
| Summarize | `src.handlers.summarize` | 結果を S3 から回収、順序復元、総評生成、レスポンス組み立て |

プロンプト構築・レスポンスパース・結果集約は **`src/evaluator.py` の関数が唯一の実装**であり、各ステップはそれを再利用するだけで再実装しない。

## 2 つの呼び出し経路

同じ定義から**2 つのステートマシン**をデプロイする。同期で返すことと大量処理は上限が相反するため、片方に寄せずに両方を用意している。

| | 同期（`-sync`） | 非同期（`-async`） |
|---|---|---|
| 種別 | Express | Standard |
| 起動 | `aws stepfunctions start-sync-execution` | `aws stepfunctions start-execution` |
| 結果の受け取り | 実行結果として即座に返る | `final/<content-hash>.json` を S3 から取得 |
| Map | Inline Map | **Distributed Map** |
| 同時実行数の上限 | 40（Inline Map の制約） | Distributed Map のため制約なし |
| 実行時間の上限 | **5 分**（Express の制約） | 6 時間（設定値） |
| 向いている場面 | 対話的な利用、クライテリア数が中程度まで | 大量の評価、クライテリア数が数十〜数百 |

Summarize は**どちらの経路でも**最終結果を S3 に書く。同期呼び出し元には戻り値としても返るので、コードパスは 1 本のまま非同期呼び出し元の取得手段が確保される。

## ステートサイズ対策（クレームチェック）

Step Functions のステート間データ上限は 256 KB。**入出力の両方**がこれを超え得る。

- **入力**: `prompt` / `response` / `contexts` は文書規模になり得る。さらに Map の各ブランチにコピーするとクライテリア数倍になる。
- **出力**: 1 件の結果は小さくても、`evaluation_steps` を伴う根拠テキストが数百件集まれば超える。

そこで payload と結果は S3 に置き、ステート間は `s3://` URI だけが流れる（[`src/jobs.py`](../src/jobs.py)）。ステートサイズが提出物のサイズにもクライテリア数にも依存しなくなる。

Summarize は結果を**並列 GET** で回収する。数百件を逐次取得するとこのステップの実行時間を支配するため。これは S3 の小さな GET であり、クライテリアの fan-out を意図的にスレッドで行わないこととは別の判断。

## 冪等性

1 件の評価は **N+1 回**のモデル呼び出しを伴うため、大量処理では重複実行のコストが無視できない。

- キーは **評価内容のハッシュ + クライテリア名 + モデル**。job URI は実行ごとに一意なので使わない（使うと永久にヒットしない）。
- 同一内容の再投入・Map のリトライは、保存済み結果を返してモデルを呼ばない。
- プロンプト・クライテリア・モデルのいずれかが変われば別キーになる。
- ハッシュは結果の S3 キーにも使われるため、キャッシュヒットが実在するオブジェクトを指し続ける。
- `IDEMPOTENCY_TABLE` 未設定時はデコレータが素通しになる（ローカル・テストで DynamoDB 不要）。**「常に評価する」への劣化であって「古い結果を返す」への劣化ではない**。

保存期間は既定 24 時間で、結果オブジェクトの保持期間（30 日）より短く設定している。

## リトライと同時実行

- リトライは **Map ステート側**（`BackoffRate: 2`、`MaxAttempts: 4`、FULL jitter）。Lambda 内で `time.sleep` しないためバックオフ中の課金が発生しない。
- `MaxConcurrency` がワークフロー定義の一部なので、呼び出し方に関係なく Bedrock への同時呼び出し数が頭打ちになる。
- Bedrock クライアントは `adaptive` リトライモード（クライアントサイドレート制限つき）。
- クライテリア 1 件でも評価できなければ**評価全体を失敗**させる（`ToleratedFailureCount: 0`）。スコアを付けられなかったクライテリアと、ジャッジが「評価不能」と判断したクライテリアは意味が違うため、前者を後者に丸めるとレスポンスは完全に見えるのに実際はルーブリックを満たしていない状態になる。

## モジュールの役割

| モジュール | 役割 |
|-----------|------|
| `handlers/prepare` | 検証・criteria 解決・ジョブ退避・content hash |
| `handlers/evaluate_criterion` | クライテリア 1 件の評価（冪等）、結果の S3 保存 |
| `handlers/summarize` | 結果回収・総評生成・レスポンス組み立て・最終結果の保存 |
| `evaluator` | ジャッジプロンプト構築、1 件評価、レスポンスパース、結果集約 |
| `criteria` | `EvaluationCriteria` / `CriterionDefinition`、S3 からの JSON 読み込み、`load_from_dict` |
| `validation` | イベント検証、モデル解決 |
| `errors` | 例外階層（全モジュール共通） |
| `jobs` | クレームチェック、content hash、結果の保存と回収 |
| `idempotency` | Powertools Idempotency の配線とキー生成 |
| `config` | 環境変数＋Secrets Manager からの `Config` |
| `providers` | `BaseProvider`、各 SDK の同期呼び出し |
| `observability` | Powertools `Tracer` / `Metrics` の共有インスタンス |

## 認証とシークレット

- **Bedrock**: Lambda 実行ロールの IAM 認証。API キー不要。
- **Anthropic / OpenAI**: Secrets Manager（`API_KEYS_SECRET_NAME`）から遅延取得し、Powertools が既定 300 秒キャッシュする。環境変数に平文で置かない。
- クロスリージョン推論プロファイル（`jp.` 等のプレフィックス付き ID）は、プロファイル ARN とルーティング先各リージョンの基盤モデル ARN の**両方**に `bedrock:InvokeModel` が要る。詳細は [`config/README.md`](../config/README.md)。

## 権限分離

ステップを 3 つの Lambda に分けたことで、ロールごとに必要最小限まで絞れている。

| | Bedrock | criteria バケット | jobs バケット | DynamoDB |
|---|---|---|---|---|
| Prepare | ✗ | 読み取り | 書き込み | ✗ |
| EvaluateCriterion | ✓ | ✗ | 読み書き（オブジェクト単位） | ✓ |
| Summarize | ✓ | ✗ | 読み書き（オブジェクト単位） | ✗ |

バケットレベルの `s3:List*` はどのロールも持たない。

## 観測性

- **ログ**: Powertools `Logger`（JSON 構造化、`correlation_id` にリクエスト ID）。ロググループは CDK が明示作成し保持期間を設定する。
- **トレース**: X-Ray 有効。レスポンス本文はトレースに含めない（提出物と講評を含むため）。ステートマシンの `includeExecutionData` も同じ理由で無効。
- **メトリクス**: CloudWatch EMF。`EvaluationsCompleted` / `EvaluationsFailed` / `CriterionEvaluationFailed` / `NotAssessableCount` / `BedrockThrottled` / `JudgeLatencyMs`。ディメンションは `provider` と `judge_model`。
- **アラーム**: Lambda エラー・スロットル・p99 実行時間・DLQ 滞留・各ワークフローの失敗を SNS に通知。
- 計装の失敗が評価を落とすことはない（`src/observability.py` の `add_count` / `add_latency_ms` は例外を握る）。
