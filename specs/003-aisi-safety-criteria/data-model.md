# Data Model: AISI AIセーフティ評価クライテリアファイル

**Branch**: `003-aisi-safety-criteria` | **Date**: 2026-03-21

## 概要

本機能の成果物は静的JSONファイル1つ。既存の `EvaluationCriteria` データモデルを変更しない。

---

## 既存スキーマ（変更なし）

### EvaluationCriteria（トップレベル）

```json
{
  "name": "string — クライテリアセット名",
  "description": "string? — クライテリアセットの説明（オプション）",
  "criteria": "[CriterionDefinition] — 評価クライテリアの配列"
}
```

### CriterionDefinition（各クライテリア）

```json
{
  "name": "string — 英語スネークケース識別子（例: harmful_content_control）",
  "description": "string — クライテリアの説明",
  "evaluation_prompt": "string? — ジャッジLLMへの追加評価指示（オプション）",
  "evaluation_steps": "list[string]? — 段階的推論ステップ（オプション）",
  "score_descriptors": "dict[str, str]? — スコア値→説明マッピング（オプション）"
}
```

---

## AISIクライテリアファイルのデータ構成

### ファイル: `criteria/aisi_safety_evaluation_criteria.json`

| フィールド | 値 |
|-----------|---|
| `name` | `"AISI AIセーフティ評価クライテリア"` |
| `description` | AISIガイド第1.10版の説明 |
| `criteria` | 10要素の配列（以下参照） |

### 10クライテリアの構成

| # | `name`（識別子） | AISI観点名 | `evaluation_steps` 数 | `score_descriptors` 数 |
|---|-----------------|-----------|----------------------|----------------------|
| ① | `harmful_content_control` | 有害情報の出力制御 | 4 | 5 |
| ② | `misinformation_prevention` | 偽誤情報の出力・誘導の防止 | 4 | 5 |
| ③ | `fairness_and_inclusivity` | 公平性と包摂性 | 4 | 5 |
| ④ | `high_risk_use_handling` | ハイリスク利用・目的外利用への対処 | 4 | 5 |
| ⑤ | `privacy_protection` | プライバシー保護 | 4 | 5 |
| ⑥ | `security_assurance` | セキュリティ確保 | 4 | 5 |
| ⑦ | `explainability` | 説明可能性 | 4 | 5 |
| ⑧ | `robustness` | ロバスト性 | 4 | 5 |
| ⑨ | `data_quality_indication` | データ品質（出力評価適用版） | 4 | 5 |
| ⑩ | `verifiability` | 検証可能性（出力評価適用版） | 4 | 5 |

---

## バリデーションルール

- `name` フィールドは英語スネークケース（英数字・アンダースコアのみ）
- `score_descriptors` のキーは `"1"` 〜 `"5"` の文字列
- `evaluation_steps` は2以上の文字列リスト
- 既存の `CriterionDefinition` Pydantic モデルで `load_from_s3()` 実行時にバリデーション済み
