# examples/ — 評価結果サンプル

実際のジャッジ実行に近い **入力** と **出力** をまとめた JSON サンプル。テストデータではなく、ドキュメント・デモ用。

| ファイル | 内容 |
|----------|------|
| [`default_evaluation_result.json`](default_evaluation_result.json) | 汎用 7 軸クライテリア（`criteria/default.json`）を想定したスコア・`criterion_reasoning`・総評の例 |
| [`disclosure_evaluation_result.json`](disclosure_evaluation_result.json) | 情報公開法第 5 条ベースのクライテリアを想定した例 |

各ファイルの `_meta` に、想定コマンドや注記がある。`input.criteria_file` は Lambda では **S3 URI** を渡す（例ではリポジトリ相対パス風の文字列で示している場合がある。本番では `s3://...` に置き換える）。
