# JSON スキーマ（契約）の場所

機械可読な契約は **リポジトリ直下の `contracts/`** に JSON Schema として置く。ディレクトリの説明は [repository-layout.md](repository-layout.md)。仕様変更時は **ハンドラとテスト**と整合させること。

## ファイル一覧

| 内容 | パス |
|------|------|
| Lambda 入力イベント（`system_prompt`・`contexts` 等） | [`contracts/lambda-event.json`](../contracts/lambda-event.json) |
| Lambda レスポンス | [`contracts/lambda-response.json`](../contracts/lambda-response.json) |
| クライテリアファイル（S3 の JSON） | [`contracts/criteria-file.json`](../contracts/criteria-file.json) |

## 実装との差分に注意

- ハンドラが受け取る追加コンテキストのフィールド名は **`contexts`**（複数形）。スキーマはこの名前に合わせている。

## 入力イベント（`lambda-event.json`）の評価モード

- **`prompt` と `response`**: どちらか一方または両方に、トリム後に空でない文字列が必要。両方とも空（または省略で実質空）のときはバリデーションエラー。
- **片側のみ**: プロンプトのみ・応答のみの評価が可能。欠けた役はジャッジ向けプロンプト内でプレースホルダ文に置き換わる。
- **`prompt_descriptor` / `response_descriptor`**: 任意。運用者向けメモをジャッジに渡す（最大長・制御文字制限はハンドラで検証）。LLM の実際のシステム／ユーザ／アシスタントメッセージと混同しないよう、スキーマ上は別フィールド。

## レスポンス（`lambda-response.json`）の assessability

- **`criterion_assessability`**: 各クライテリア名に対し `assessed` または `not_assessable`（必須）。
- **`criterion_scores`**: `assessed` のクライテリアに限り数値スコアを含む。`not_assessable` の項目はキーを持たない（空オブジェクトもあり得る）。
- **`criterion_reasoning`**: 評価不能のクライテリアも理由文字列を返す。

## 長文仕様・spec-kit 作業用

- **`specs/`** は Git 管理外（[`.gitignore`](../.gitignore)）。ローカルで spec-kit 等を使う場合のみ配置する。

## クライテリアの例

- リポジトリ内の実データ: [`criteria/`](../criteria/README.md)
- 入出力サンプル: [`examples/`](../examples/README.md)
