# criteria/ — 評価クライテリア定義

LLM-as-a-Judge システムで使用する評価クライテリア（審査基準）の設定ファイル群。より広いドキュメント索引は [docs/README.md](../docs/README.md)。


**クライテリアは使用前に S3 へアップロードが必須**。Lambda はリポジトリ内の `criteria/*.json` を直接読まず、イベントの `criteria_file` に渡された **S3 URI**（例: `s3://my-bucket/criteria/default.json`）からのみ取得する。リポジトリ内の JSON は編集・レビュー・バージョン管理用。

```bash
# 例: default.json を S3 にアップロード
aws s3 cp criteria/default.json s3://my-bucket/criteria/default.json
```

Lambda 実行ロールに対象バケットの `s3:GetObject` が必要（[`config/parameters.json`](../config/parameters.json) の `criteria_bucket_arn` または `CRITERIA_BUCKET_ARN=...` 環境変数で `scripts/deploy.sh` 経由付与）。

## ファイル一覧

```
criteria/
├── README.md                           # このファイル
├── default.json                        # 汎用評価クライテリア（7 軸、段階的推論付き）
└── disclosure_evaluation_criteria.json # 情報公開法第 5 条評価基準（6 条号、段階的推論付き）
```

---

## default.json — 汎用評価クライテリア

LLM 回答の汎用的な品質評価に使用する 7 軸のクライテリアセット。各クライテリアに `evaluation_steps`（段階的チェックリスト）が定義されており、ジャッジ LLM が論拠を示しながらスコアリングする。

### クライテリア一覧

| name | 日本語名 | 測定内容 | evaluation_steps 数 |
|------|---------|---------|-------------------|
| `accuracy` | 正確性 | 事実的正確性と信頼性 | 3 ステップ |
| `completeness` | 網羅性 | 回答の包括性と深度 | 3 ステップ |
| `relevance` | 関連性 | 質問への適合度 | 3 ステップ |
| `clarity` | 明瞭性 | 表現の分かりやすさ | 3 ステップ |
| `helpfulness` | 有用性 | 読者にとっての実用的価値 | 3 ステップ |
| `coherence` | 一貫性 | 論理的な流れと整合性 | 3 ステップ |
| `appropriateness` | 適切性 | 学術的文脈における適切さ | 3 ステップ |

### 使用例（Lambda イベント）

```json
{
  "prompt": "量子コンピュータと古典コンピュータの違いを説明してください。",
  "response": "量子コンピュータは量子ビット（qubit）を使用し...",
  "provider": "anthropic",
  "criteria_file": "s3://my-bucket/criteria/default.json"
}
```

評価サンプル（入出力）: [`examples/default_evaluation_result.json`](../examples/default_evaluation_result.json)

---

## disclosure_evaluation_criteria.json — 情報公開法第 5 条評価基準

情報公開法（平成 11 年法律第 42 号）第 5 条第 1 号〜第 6 号に基づく不開示事由の該当性を判定するクライテリアセット。行政文書の開示・不開示判断を支援する。

### クライテリア一覧

| name | 条号 | 不開示事由 | evaluation_steps 数 |
|------|------|----------|-------------------|
| `article_5_1` | 第 5 条第 1 号 | 個人情報保護 | 6 ステップ |
| `article_5_2` | 第 5 条第 2 号 | 法人等情報保護 | 4 ステップ |
| `article_5_3` | 第 5 条第 3 号 | 国家安全保障 | 3 ステップ |
| `article_5_4` | 第 5 条第 4 号 | 公共の安全と秩序 | 1 ステップ |
| `article_5_5` | 第 5 条第 5 号 | 内部審議等 | 4 ステップ |
| `article_5_6` | 第 5 条第 6 号 | 行政運営等 | 7 ステップ |

各クライテリアの `evaluation_prompt` には以下が含まれる：

- **段階的評価手順**（段階 1〜3/4）: YES/NO で回答するチェックリスト
- **評価ガイドライン**: 観点ごとの優先事項と評価プロセス
- **参照条文**: 情報公開法の該当条文（完全版）

### スコア解釈

| スコア | 意味 |
|-------|------|
| 1 | 明確に不開示事由に該当し、不開示が必要 |
| 2 | 不開示事由に該当し、不開示が適切 |
| 3 | 不開示事由の該当性があり、慎重な検討が必要 |
| 4 | 不開示事由の該当性は低く、開示を検討可能 |
| 5 | 不開示事由に該当せず、開示が適切 |

**スコア閾値**: 4.0 以上 = 開示 / 2.5〜4.0 未満 = 要検討（部分開示含む） / 2.5 未満 = 不開示

### 使用例（Lambda イベント）

```json
{
  "prompt": "情報公開請求対象: 農林水産省の補助金交付先企業に対する財務審査記録（2024年度）。当該記録には申請企業の財務諸表詳細分析、審査担当職員の判定根拠、内部審議経緯、次年度の審査基準改定案が含まれる。",
  "response": "本文書には申請企業の詳細な財務情報（収益構造・借入状況等）が含まれており、企業の競争上の地位に関わる情報である。また審査担当職員の判断過程や内部審議経緯が記録されており、行政の内部意思決定プロセスを反映している。次年度審査基準改定案については現時点での公開は行政運営上の支障をきたす可能性がある。",
  "provider": "anthropic",
  "criteria_file": "s3://my-bucket/criteria/disclosure_evaluation_criteria.json"
}
```

評価サンプル（入出力）: [`examples/disclosure_evaluation_result.json`](../examples/disclosure_evaluation_result.json)

---

## クライテリアファイルの形式

```json
{
  "name": "クライテリアセット名",
  "description": "（任意）クライテリアセットの説明",
  "criteria": [
    {
      "name": "criterion_identifier",
      "description": "このクライテリアが測定する内容",
      "evaluation_prompt": "ジャッジ LLM への詳細ガイダンス（任意）",
      "evaluation_steps": [
        "ステップ 1 の評価質問（任意）",
        "ステップ 2 の評価質問"
      ],
      "score_descriptors": {
        "1": "スコア 1 の説明（任意）",
        "3": "スコア 3 の説明",
        "5": "スコア 5 の説明"
      }
    }
  ]
}
```

### フィールド仕様

| フィールド | 必須 | 型 | 制約 |
|-----------|------|-----|------|
| `name` | ✅ | string | 英数字・アンダースコアのみ（`^[a-zA-Z0-9_]+$`） |
| `description` | ✅ | string | 空文字列不可 |
| `evaluation_prompt` | ✗ | string | ジャッジへの追加指示 |
| `evaluation_steps` | ✗ | string[] | 各ステップの評価質問リスト |
| `score_descriptors` | ✗ | object | スコア文字列 → 説明テキスト |

---

## カスタムクライテリアの作成

### 手順

1. `default.json` を参考に新しい JSON ファイルを作成する
2. `criteria` 配列に評価軸を定義する
3. S3 バケットにアップロードする
4. Lambda イベントの `criteria_file` に S3 URI を指定する

### evaluation_steps の設計指針

- 各ステップは「YES / NO」で回答できる具体的な質問にする
- 複雑な判断を小さな確認ステップに分解することで推論の透明性が向上する
- 法的判断・リスク評価など複数の条件を順次確認する場面で特に有効

```json
{
  "evaluation_steps": [
    "回答は質問のすべての側面に対応しているか？",
    "重要な情報の欠落や省略はないか？",
    "各側面の説明の深度は質問の難易度に比例しているか？"
  ]
}
```

### ベストプラクティス

- **name**: 英数字とアンダースコアを使った説明的な識別子（例: `legal_accuracy`, `article_5_1`）
- **description**: 評価軸の意図を 1〜2 文で端的に記述する
- **evaluation_prompt**: 評価の観点・手順・注意事項を詳しく記述する（省略可だが複雑な基準では推奨）
- **evaluation_steps**: 最大 6〜8 ステップ程度が適切。多すぎると LLM の出力が冗長になる
- **score_descriptors**: スコア 1・3・5 の 3 点または 1〜5 全点に説明を付けると精度が向上する
