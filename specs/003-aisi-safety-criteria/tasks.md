---

description: "Task list for AISI AIセーフティ評価クライテリアファイル"
---

# Tasks: AISI AIセーフティ評価クライテリアファイル

**Input**: Design documents from `/specs/003-aisi-safety-criteria/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: User story this task belongs to (US1, US2)
- File paths are absolute from repo root

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: 既存スキーマとの互換性を確認し、クライテリアファイルを配置する。ソースコード変更なし。

**⚠️ CRITICAL**: User Story フェーズはこのフェーズの完了に依存する。

- [X] T001 [P] `criteria/aisi_safety_evaluation_criteria.json` を作成し、AISI評価観点ガイド第1.10版の10クライテリアを既存スキーマ（`name`・`description`・`evaluation_prompt`・`evaluation_steps`・`score_descriptors`）に従って記述する
- [X] T002 [P] JSON バリデーション：`python3 -c "import json; json.load(open('criteria/aisi_safety_evaluation_criteria.json'))"` を実行して構文エラーがないことを確認する

**Checkpoint**: クライテリアファイルが配置され、JSONとして有効であること。

---

## Phase 2: User Story 1 — AISIフレームワークによるAIセーフティ評価 (Priority: P1) 🎯 MVP

**Goal**: 10のAISI評価観点すべてが正しい識別子・説明・評価プロンプトでクライテリアファイルに含まれ、`load_from_s3()` と互換性があることを検証する。

**Independent Test**: `criteria/aisi_safety_evaluation_criteria.json` を Python で読み込み、10クライテリア全てに `name`・`description`・`score_descriptors`（1〜5）が揃っていることを確認する。

- [X] T003 [US1] クライテリア名の検証：10観点のスネークケース識別子（`harmful_content_control`, `misinformation_prevention`, `fairness_and_inclusivity`, `high_risk_use_handling`, `privacy_protection`, `security_assurance`, `explainability`, `robustness`, `data_quality_indication`, `verifiability`）が全て含まれることを確認する
- [X] T004 [US1] `score_descriptors` の完全性検証：全10クライテリアの `score_descriptors` に `"1"` 〜 `"5"` の5段階が全て定義されていることを確認する
- [X] T005 [US1] `evaluation_prompt` の検証：全10クライテリアに `evaluation_prompt` が存在し、空文字でないことを確認する

**Checkpoint**: User Story 1 が完全に機能し、独立して検証可能。Python で全10クライテリアの必須フィールドを確認する。

---

## Phase 3: User Story 2 — 段階的推論による評価透明性の確保 (Priority: P2)

**Goal**: 全10クライテリアに2以上の `evaluation_steps` が定義されており、ジャッジLLMが段階的推論を実行できることを検証する。

**Independent Test**: `criteria/aisi_safety_evaluation_criteria.json` を読み込み、全クライテリアの `evaluation_steps` が2以上の文字列リストであることを確認する。

- [X] T006 [US2] `evaluation_steps` の完全性検証：全10クライテリアに `evaluation_steps` が存在し、それぞれ4つの評価ステップ（問い）が含まれることを確認する
- [X] T007 [US2] `evaluation_steps` の内容品質確認：各ステップが「〜か？」形式の具体的な判断可能な問いであり、AISI観点の評価軸（有害性・偽誤情報・公平性・セキュリティ等）を適切にカバーしていることをレビューする

**Checkpoint**: User Story 2 が完全に機能。全10クライテリアで `evaluation_steps` による段階的推論が実行可能。

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: ドキュメント更新、構成確認、AISIガイドとの整合性チェック。

- [X] T008 [P] `README.md` の `criteria/` ディレクトリ構造セクションに `aisi_safety_evaluation_criteria.json` を追記する（プロジェクト構造ツリーおよびクライテリアファイルの説明欄）
- [X] T009 [P] 構成確認：`criteria/aisi_safety_evaluation_criteria.json` にスペック番号（`FR-xxx`・`SC-xxx`・`T0xx`）が含まれていないことを確認する（Constitution Principle III 準拠）
- [X] T010 既存クライテリアファイルとの互換性最終確認：`default.json` および `disclosure_evaluation_criteria.json` と同一のトップレベル構造（`name`・`criteria`・各クライテリアの必須フィールド）を持つことを Python で検証する

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: No dependencies — start immediately
- **User Story 1 (Phase 2)**: Depends on T001–T002 (クライテリアファイル存在・JSON有効性)
- **User Story 2 (Phase 3)**: Depends on T001–T002; US1 と独立して実行可能
- **Polish (Phase 4)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Phase 1 完了後に開始可能
- **US2 (P2)**: Phase 1 完了後に開始可能（US1 と独立）

### Parallel Opportunities

```bash
# Phase 1 — ファイル作成とバリデーションは並列実行可能:
Task: "Create criteria/aisi_safety_evaluation_criteria.json"  # T001
Task: "Validate JSON syntax"                                   # T002 (after T001)

# Phase 2+3 — 異なる観点を並列検証:
Task: "Validate score_descriptors completeness"  # T004 (after T003)
Task: "Validate evaluation_prompt presence"      # T005 (after T003)

# Phase 4 — Polish tasks in parallel:
Task: "Update README.md criteria directory listing"  # T008
Task: "Verify no spec IDs in criteria file"          # T009
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (T001–T002) — クライテリアファイル作成・JSON検証
2. Complete Phase 2 (T003–T005) — 10観点の必須フィールド検証
3. **STOP and VALIDATE**: `python3 -c "import json; data=json.load(open('criteria/aisi_safety_evaluation_criteria.json')); assert len(data['criteria'])==10"` — passes
4. Deploy by uploading to S3 if ready

### Incremental Delivery

1. Phase 1 → Foundation (クライテリアファイル配置完了)
2. Phase 2 → US1 完了 → 10観点の評価が機能する
3. Phase 3 → US2 完了 → 段階的推論が機能する
4. Phase 4 → Polish → ドキュメント更新・最終確認

---

## Notes

- [P] tasks = different files or genuinely independent within a phase
- ソースコード（`src/`・`tests/`）への変更は不要
- 新規 Python モジュール不要 — 既存の `CriterionDefinition` スキーマがそのまま動作する
- AISI ガイドが閾値を規定しないため、スコア 1〜5 のルーブリックは独自定義（research.md Decision 3 参照）
- マルチモーダル評価項目は除外（research.md Decision 2 参照）
