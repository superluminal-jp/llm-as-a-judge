# Implementation Plan: AISI AIセーフティ評価クライテリアファイル

**Branch**: `003-aisi-safety-criteria` | **Date**: 2026-03-21 | **Spec**: [spec.md](./spec.md)

## Summary

日本AIセーフティ・インスティテュート（AISI）「AIセーフティに関する評価観点ガイド」第1.10版（2025年3月28日）に定義された10の評価観点を、既存の criteria JSON フォーマットに変換した静的データファイル `criteria/aisi_safety_evaluation_criteria.json` を追加する。ソースコード変更なし。既存の `CriterionDefinition` スキーマおよび `load_from_s3()` とのフル互換性を保つ。

## Technical Context

**Language/Version**: JSON (static data file — no Python changes)
**Primary Dependencies**: `src/criteria.py`（`EvaluationCriteria`・`CriterionDefinition` スキーマ、`load_from_s3()`）
**Storage**: `criteria/` ディレクトリ（開発環境）、S3（本番環境 — 既存のS3ローダー経由）
**Testing**: pytest（既存の `test_criteria.py` が `CriterionDefinition` スキーマを検証済み）
**Target Platform**: AWS Lambda（`criteria_file` フィールドでS3 URIを指定してロード）
**Project Type**: Configuration / データファイル
**Performance Goals**: N/A（静的ファイル読み込み）
**Constraints**: 既存 `EvaluationCriteria` スキーマと完全互換（`name`・`description`・`evaluation_prompt`・`evaluation_steps`・`score_descriptors` フィールド）
**Scale/Scope**: 10クライテリア × 4ステップ × 5スコア記述

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Living Documentation — docs updated in same commit | ✅ | README の `criteria/` ディレクトリ構造欄にファイル追記が必要 |
| II. Production-Grade Observability — structured logging, error hierarchy, why-comments | ✅ | ソースコード変更なし。静的JSONファイルのため対象外 |
| III. Codebase Clarity — no spec IDs or spec-workflow terms in src/ or tests/ | ✅ | JSONファイルにはAISI観点名のみ記載。仕様番号（FR-xxx等）は使用しない |
| IV. Minimal Structure — stateless, no unnecessary modules, YAGNI | ✅ | 新規Pythonモジュール不要。既存スキーマをそのまま利用 |
| V. Test Coverage — ≥ 90%, no real API calls, tests assert behaviour | ✅ | 新規Pythonコードなし。既存スキーマ互換性はJSONバリデーションで確認済み |

全原則 ✅ — Phase 0 に進む。

## Project Structure

### Documentation (this feature)

```text
specs/003-aisi-safety-criteria/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── criteria-schema.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
criteria/
├── default.json                        # 既存 — 変更なし
├── disclosure_evaluation_criteria.json # 既存 — 変更なし
└── aisi_safety_evaluation_criteria.json  # 新規追加（このfeatureの成果物）

README.md                               # criteria/ ディレクトリ欄に追記
```

**Structure Decision**: `criteria/` ディレクトリへの JSON ファイル追加のみ。`src/` への変更なし。既存の S3 ローダー・スキーマと完全互換。

## Complexity Tracking

> 全原則が ✅ のため、本セクションへの記載は不要。
