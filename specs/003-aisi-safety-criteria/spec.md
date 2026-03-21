# Feature Specification: AISI AIセーフティ評価クライテリアファイル

**Feature Branch**: `003-aisi-safety-criteria`
**Created**: 2026-03-21
**Status**: Draft
**Source**: 日本AIセーフティ・インスティテュート「AIセーフティに関する評価観点ガイド」第1.10版（2025年3月28日）

## 概要

日本AIセーフティ・インスティテュート（AISI）が定義した10の評価観点に基づいて、LLM-as-a-Judge システムで利用できる評価クライテリア（criteria）JSONファイルを作成する。既存の `criteria/default.json` および `criteria/disclosure_evaluation_criteria.json` と同一の形式を踏襲し、`criteria/aisi_safety_evaluation_criteria.json` として提供する。

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - AISIフレームワークによるAIセーフティ評価 (Priority: P1)

AIシステムの安全性を体系的に評価したいユーザー（AI開発者・監査担当者・政策立案者）が、AISIの10観点に基づいてLLM出力を評価できる。クライテリアファイルを Lambda イベントの `criteria_file` フィールドに指定するだけで、AISI準拠の多角的安全評価を実行できる。

**Why this priority**: AISI の評価観点は日本の公的機関が定めた標準フレームワークであり、このガイドに準拠した評価ができることは本機能の核心的価値である。

**Independent Test**: クライテリアファイルを `criteria_file` として Lambda に渡し、10クライテリア全てのスコアと推論が返却されることを確認する。

**Acceptance Scenarios**:

1. **Given** AISI クライテリアファイルが `criteria/` ディレクトリに配置されている状態で、**When** `criteria_file` にそのファイルパスを指定してLLM出力を評価する、**Then** AISI の10観点全てに対するスコア（1〜5）と推論テキストが返却される。
2. **Given** 有害情報を含む可能性のある回答を評価対象として、**When** 評価を実行する、**Then** ① 有害情報の出力制御（harmful_content_control）観点で適切な低スコアと具体的な根拠が返却される。
3. **Given** 複数の評価観点が適用可能な回答を評価対象として、**When** 評価を実行する、**Then** 各観点が独立してスコアリングされ、観点間の重み付けなしに個別の結果が得られる。

---

### User Story 2 - 段階的推論による評価透明性の確保 (Priority: P2)

評価担当者が各クライテリアの判断根拠を把握し、監査・レポート作成に活用できる。`evaluation_steps` による段階的推論によって、スコアの根拠が明示される。

**Why this priority**: AIセーフティ評価は組織の意思決定に直結するため、スコアだけでなく推論過程の透明性が不可欠。

**Independent Test**: 任意のクライテリア1つを指定して評価を実行し、`criterion_reasoning` に各ステップの回答と最終判断が含まれることを確認する。

**Acceptance Scenarios**:

1. **Given** `evaluation_steps` が定義されたクライテリアで評価を実行した状態で、**When** `criterion_reasoning` を参照する、**Then** 各ステップへの回答と最終判断（Final:）が含まれる。
2. **Given** 評価結果を審査・監査に提出する必要がある状況で、**When** 評価結果の `criterion_reasoning` を確認する、**Then** スコア根拠として第三者が理解できる説明が含まれている。

---

### Edge Cases

- 評価対象の回答が複数の安全観点に同時に違反する場合、各観点は独立してスコアリングされる。
- `system_prompt` が提供されている場合、④ ハイリスク利用（high_risk_use）クライテリアはシステムプロンプトで定義された意図した用途との乖離を考慮する。
- AIセーフティ観点の中で評価対象に適用しにくい観点（例：⑨ データ品質は出力評価には直接適用困難）は、LLMシステムへの直接評価可能な側面にフォーカスしてスコアリングする。
- スコア 1〜5 の評価基準はAISIガイドが定義しておらず、本クライテリアファイル内で実用的なルーブリックを独自に定義する。

---

## Requirements *(mandatory)*

### Functional Requirements

- 評価クライテリアファイルは `criteria/aisi_safety_evaluation_criteria.json` に配置する
- クライテリア名（`name`）はAISIの観点名に対応する英語スネークケース識別子を使用する
- 各クライテリアには `description`（観点の説明）、`evaluation_prompt`（ジャッジLLMへの評価指示）、`evaluation_steps`（段階的推論ステップ）、`score_descriptors`（スコア1〜5の説明）を含める
- 10の評価観点すべてを網羅する：有害情報の出力制御、偽誤情報の防止、公平性と包摂性、ハイリスク利用への対処、プライバシー保護、セキュリティ確保、説明可能性、ロバスト性、データ品質、検証可能性
- スコア記述（`score_descriptors`）はAISIの「許容範囲内か否か」の基準を1〜5の段階スコアに変換した実用的なルーブリックとする
- `evaluation_steps` は各観点につき2〜4の具体的かつ判断可能な問いとして定義する
- クライテリア名・説明・評価プロンプトは日本語で記述し、AIセーフティの専門用語を正確に使用する
- 既存のクライテリアJSONファイル（`default.json`、`disclosure_evaluation_criteria.json`）と完全に互換性のある構造とする
- クライテリアファイルはLLMシステム全体の出力評価に適用でき、データ品質・検証可能性のようなプロセス観点は出力から推測可能な範囲でスコアリングできるよう評価プロンプトを調整する

### Key Entities

- **評価クライテリア（Criterion）**: `name`（識別子）、`description`（説明）、`evaluation_prompt`（評価指示）、`evaluation_steps`（推論ステップ）、`score_descriptors`（スコア記述）の5フィールドで構成されるJSONオブジェクト
- **AISIクライテリアファイル**: 10クライテリアを含む `criteria` 配列と `name`・`description` を持つトップレベルJSONオブジェクト

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- AISI ガイド第1.10版で定義された10の評価観点が全て網羅されている（10/10）
- 各クライテリアの `evaluation_steps` が2ステップ以上含まれる（評価の段階的透明性を担保）
- 既存のクライテリアファイルと構造的互換性があり、同じ Lambda 呼び出しで読み込み・評価が実行できる
- LLM-as-a-Judge による実際の評価において、全クライテリアでスコアと推論が返却される（エラー率 0%）
- 各クライテリアのスコア記述が 1〜5 全て定義されており、ジャッジLLMが判断の根拠として参照できる

---

## Assumptions

- 評価対象はLLMシステムの出力（テキスト）であり、マルチモーダル評価（画像を含む入力）には対応しない（AISIガイドのマルチモーダル拡張部分は除外）
- 適切な閾値（acceptable range）はAISIガイドが規定しておらず、本クライテリアの 1〜5 スコアはユースケースに応じてユーザーが解釈する
- ⑨ データ品質および ⑩ 検証可能性は、LLMシステム全体のプロセスではなく、評価対象の出力テキストから判断できる範囲（出力の信頼性・根拠明示性）を評価する
- クライテリアは日本語で記述するが、ジャッジLLMとして日本語対応のモデルを使用することを前提とする

---

## Dependencies

- 既存クライテリア形式: `criteria/default.json`、`criteria/disclosure_evaluation_criteria.json`
- AISIガイド第1.10版: https://aisi.go.jp/assets/pdf/ai_safety_eval_v1.10_ja.pdf
- AISIガイド概要版第1.10版: https://aisi.go.jp/assets/pdf/ai_safety_eval_summary_v1.10_ja.pdf
