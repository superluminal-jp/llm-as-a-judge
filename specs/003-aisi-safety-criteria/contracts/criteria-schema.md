# Contract: AISIクライテリアファイルスキーマ

**Branch**: `003-aisi-safety-criteria` | **Date**: 2026-03-21

## 概要

`criteria/aisi_safety_evaluation_criteria.json` が準拠するJSONスキーマ。既存の `CriterionDefinition` データクラス（`src/criteria.py`）と完全互換。

---

## JSONスキーマ（既存スキーマと同一）

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "EvaluationCriteria",
  "type": "object",
  "required": ["name", "criteria"],
  "properties": {
    "name": {
      "type": "string",
      "description": "クライテリアセットの名称"
    },
    "description": {
      "type": "string",
      "description": "クライテリアセットの説明（オプション）"
    },
    "criteria": {
      "type": "array",
      "minItems": 1,
      "items": {
        "$ref": "#/definitions/CriterionDefinition"
      }
    }
  },
  "definitions": {
    "CriterionDefinition": {
      "type": "object",
      "required": ["name", "description"],
      "properties": {
        "name": {
          "type": "string",
          "pattern": "^[a-z0-9_]+$",
          "description": "英語スネークケース識別子"
        },
        "description": {
          "type": "string",
          "description": "クライテリアの説明"
        },
        "evaluation_prompt": {
          "type": "string",
          "description": "ジャッジLLMへの追加評価指示"
        },
        "evaluation_steps": {
          "type": "array",
          "items": { "type": "string" },
          "minItems": 1,
          "description": "段階的推論ステップ"
        },
        "score_descriptors": {
          "type": "object",
          "additionalProperties": { "type": "string" },
          "description": "スコア値（\"1\"〜\"5\"）→説明マッピング"
        }
      }
    }
  }
}
```

---

## Lambda インターフェース

### 入力イベント（関連フィールド）

```json
{
  "prompt": "評価対象LLMに与えたプロンプト",
  "response": "評価対象LLMの回答",
  "criteria_file": "s3://your-bucket/criteria/aisi_safety_evaluation_criteria.json"
}
```

### 出力（期待されるレスポンス構造）

```json
{
  "criterion_scores": {
    "harmful_content_control": 4,
    "misinformation_prevention": 5,
    "fairness_and_inclusivity": 4,
    "high_risk_use_handling": 4,
    "privacy_protection": 5,
    "security_assurance": 5,
    "explainability": 3,
    "robustness": 4,
    "data_quality_indication": 4,
    "verifiability": 3
  },
  "criterion_reasoning": {
    "harmful_content_control": "Step 1: ...\nStep 2: ...\nStep 3: ...\nStep 4: ...\n\nFinal: ...",
    "...": "..."
  },
  "reasoning": "総評: 各クライテリアの評価結果は以下のとおりである。...",
  "judge_model": "claude-sonnet-4-6",
  "provider": "anthropic"
}
```

---

## 互換性確認

```bash
# JSON バリデーション
python3 -c "
import json
with open('criteria/aisi_safety_evaluation_criteria.json') as f:
    data = json.load(f)
assert 'name' in data and 'criteria' in data
assert len(data['criteria']) == 10
for c in data['criteria']:
    assert 'name' in c and 'description' in c
    assert all(k in c.get('score_descriptors', {}) for k in ['1','2','3','4','5'])
print('✓ Schema validation passed')
"
```
