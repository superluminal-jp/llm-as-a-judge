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

## 長文仕様・spec-kit 作業用

- **`specs/`** は Git 管理外（[`.gitignore`](../.gitignore)）。ローカルで spec-kit 等を使う場合のみ配置する。

## クライテリアの例

- リポジトリ内の実データ: [`criteria/`](../criteria/README.md)
- 入出力サンプル: [`examples/`](../examples/README.md)
