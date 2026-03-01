# Tasks: Lambda Minimal Restructure

**Input**: `specs/001-lambda-minimal-restructure/`
**Branch**: `001-lambda-minimal-restructure`
**Generated**: 2026-03-01

**Organization**: Tasks are grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no mutual dependencies)
- **[Story]**: User story label (US1, US2, US3)
- Tests are **included** (spec AC7 requires pytest coverage)

## Library Versions (latest as of 2026-03)

```
anthropic>=0.49.0
openai>=1.68.0
boto3>=1.37.0
aws-lambda-powertools>=3.6.0
aws-cdk-lib>=2.190.0
constructs>=10.4.0
pytest>=8.3.0
pytest-cov>=6.1.0
moto[s3]>=5.1.0
```

---

## Phase 1: Setup — 既存コード削除・プロジェクト構造作成

**Purpose**: 旧 DDD 構成を削除し、新しいフラット構成を作成する

- [X] T001 既存 `src/llm_judge/` ディレクトリを削除する（`git rm -r src/llm_judge/`）
- [X] T002 既存 `tests/unit/` および `tests/integration/` ディレクトリを削除する（`git rm -r tests/`）
- [X] T003 新しいディレクトリ構造を作成する: `src/providers/`, `tests/`, `cdk/`, `scripts/`
- [X] T004 [P] `requirements.txt` を作成する（Lambda ランタイム依存: anthropic, openai, boto3, aws-lambda-powertools 最新版）
- [X] T005 [P] `requirements-dev.txt` を作成する（pytest>=8.3.0, pytest-cov>=6.1.0, moto[s3]>=5.1.0）
- [X] T006 [P] `cdk/requirements.txt` を作成する（aws-cdk-lib>=2.190.0, constructs>=10.4.0）
- [X] T007 [P] `cdk.json` を作成する（`"app": "python3 cdk/app.py"`, context: provider/criteria_bucket_arn）

**Checkpoint**: 空の新構成が存在し、旧コードが削除されている

---

## Phase 2: Foundational — 共通基盤（全 US が依存）

**Purpose**: 例外定義・設定管理・評価基準・プロバイダー抽象化

⚠️ **CRITICAL**: このフェーズが完了するまで US1〜US3 は着手不可

- [X] T008 `src/handler.py` に例外階層と Powertools Logger のみ実装する（`lambda_handler` 本体は US1 で実装）
  - `LlmJudgeError`, `ValidationError`, `ConfigurationError`, `ProviderError`, `CriteriaLoadError`
  - `logger = Logger(service="llm-judge")` モジュールレベルで定義
  - Google スタイル docstring・モジュール docstring を記述
- [X] T009 [P] `src/config.py` を実装する
  - `@dataclass(frozen=True)` の `Config` クラス（全環境変数フィールド）
  - `get_config() -> Config`（コールドスタートキャッシュ: `_config: Config | None = None`）
  - `validate_for_provider(config, provider)` → 必要 API キー欠落時に `ConfigurationError` を raise
  - `# Cold-start: initialized once per container` コメントをキャッシュ変数に付与
- [X] T010 [P] `src/criteria.py` を実装する（移植元: `src/llm_judge/domain/evaluation/criteria.py`）
  - `CriterionDefinition` (frozen dataclass, バリデーション `__post_init__`)
  - `EvaluationCriteria` (weight 正規化ロジック含む)
  - `DefaultCriteria.balanced()` のみ残す（他メソッド不要）
  - `load_from_dict(data: dict) -> EvaluationCriteria`（S3 JSON の dict から構築）
  - 削除: `CriteriaBuilder`, `parse_criteria_string`, `WeightConfigParser`, テンプレート関連
- [X] T011 [P] `src/providers/__init__.py` を実装する
  - `BaseProvider` Protocol（`complete(messages, model, timeout) -> str`）
  - `_cache: dict[str, BaseProvider] = {}` モジュールレベルキャッシュ（コールドスタートコメント付き）
  - `get_provider(name, config) -> BaseProvider` ファクトリ関数
  - `_validate_s3_uri(s3_uri: str) -> tuple[str, str]`（bucket, key を返す）

**Checkpoint**: 基盤モジュール完成。US1〜US3 を並列着手可能

---

## Phase 3: User Story 1 — Anthropic プロバイダーによる基本評価 (P1) 🎯 MVP

**Goal**: `lambda_handler(event, context)` がデフォルト評価基準で Anthropic を使って同期評価を実行できる

**Acceptance Criteria**: AC1（ハンドラー仕様）, AC3（デフォルト基準）, AC5（バリデーション）, AC6（プロバイダーエラー）

**Independent Test**: `pytest tests/test_handler.py tests/test_evaluator.py tests/test_providers.py::TestAnthropicProvider`

### US1 テスト

- [X] T012 [P] [US1] `tests/conftest.py` を作成する
  - `mock_anthropic_response` fixture（正常な評価 JSON を返す `MagicMock`）
  - `sample_event` fixture（`{"prompt": "Q", "response": "A"}`）
  - `lambda_context` fixture（`MagicMock(aws_request_id="test-req-id")`）
- [X] T013 [P] [US1] `tests/test_handler.py` を作成する（US1 スコープ）
  - `test_basic_evaluation_success` — デフォルト基準で評価成功、レスポンス schema 確認
  - `test_missing_prompt_raises_validation_error` — AC5
  - `test_missing_response_raises_validation_error` — AC5
  - `test_provider_error_propagates` — AC6（Anthropic が例外 → `ProviderError` が raise される）
  - `test_default_provider_used_when_not_specified` — 環境変数のデフォルト確認
- [X] T014 [P] [US1] `tests/test_evaluator.py` を作成する
  - `test_build_evaluation_prompt_contains_criteria` — プロンプトに基準名が含まれる
  - `test_parse_valid_json_response` — 正常 JSON → `EvaluationResult` dict
  - `test_parse_invalid_json_raises_provider_error` — 不正 JSON → `ProviderError`
  - `test_overall_score_is_weighted_average` — 重み付き平均の計算検証
- [X] T015 [P] [US1] `tests/test_providers.py` に `TestAnthropicProvider` クラスを作成する
  - `test_complete_returns_text` — `anthropic.Anthropic.messages.create` をモック
  - `test_auth_error_raises_provider_error` — `anthropic.AuthenticationError` → `ProviderError`
  - `test_rate_limit_raises_provider_error` — `anthropic.RateLimitError` → `ProviderError`
  - `test_client_cached_across_calls` — 2 回呼んでも `Anthropic()` は 1 回だけ呼ばれる

### US1 実装

- [X] T016 [US1] `src/providers/anthropic.py` を実装する（移植元: `infrastructure/clients/anthropic_client.py`）
  - 同期 `anthropic.Anthropic` クライアント（`max_retries=3`, `timeout=config.request_timeout`）
  - `# Cold-start: Anthropic client initialized once per container` コメント付きキャッシュ
  - `complete(messages, model, timeout) -> str` — SDK 呼び出しと例外マッピング
  - 例外マッピング: `anthropic.AuthenticationError` / `RateLimitError` / `APIError` → `ProviderError`
  - Google スタイル docstring（Args / Returns / Raises）
- [X] T017 [US1] `src/evaluator.py` を実装する（移植元: `infrastructure/clients/multi_criteria_client.py`）
  - `build_evaluation_prompt(prompt, response, criteria) -> str`
  - `parse_evaluation_response(raw_text, criteria, judge_model, provider) -> dict`
    - JSON 抽出（コードブロック除去含む）
    - criterion_scores のバリデーション（全基準名の存在確認）
    - 加重平均による `overall_score` 計算
    - 失敗時 → `ProviderError` を raise
  - `evaluate(prompt, response, criteria, provider, model, timeout) -> dict`
  - `logger.debug()` でプロンプト・レスポンス原文をログ（`LOG_LEVEL=DEBUG` 時のみ）
- [X] T018 [US1] `src/handler.py` の `lambda_handler` 本体を実装する（Anthropic + デフォルト基準パスのみ）
  - `@logger.inject_lambda_context(log_event=False)` デコレーター
  - `_validate_event(event)` — `prompt`/`response` 欠落・空文字を `ValidationError`
  - `config = get_config()`, `validate_for_provider(config, provider)`
  - `criteria = DefaultCriteria.balanced()`（`criteria_file` 未指定時）
  - `provider = get_provider(provider_name, config)`
  - `evaluate(...)` 呼び出し
  - `logger.info("Evaluation completed", extra={"overall_score": ..., "provider": ..., "model": ...})`
  - 例外は全て `raise`（return しない）

**Checkpoint**: `pytest tests/test_handler.py tests/test_evaluator.py -k "not s3 and not openai and not bedrock"` が全パス

---

## Phase 4: User Story 2 — マルチプロバイダー + S3 criteria (P2)

**Goal**: OpenAI / Bedrock プロバイダーを追加し、S3 から criteria JSON を読み込める

**Acceptance Criteria**: AC2（3 プロバイダー切り替え）, AC4（S3 criteria ロード）, AC7（全テストパス）

**Independent Test**: `pytest tests/` — 全テスト（moto で S3 をモック）

### US2 テスト

- [X] T019 [P] [US2] `tests/test_providers.py` に `TestOpenAIProvider` と `TestBedrockProvider` を追加する
  - OpenAI: `openai.OpenAI.chat.completions.create` をモック、例外マッピングを検証
  - Bedrock: `boto3.client.invoke_model` をモック、`ClientError` → `ProviderError` を検証
- [X] T020 [P] [US2] `tests/test_criteria.py` を作成する
  - `test_load_from_dict_valid` — 正常 dict → `EvaluationCriteria`
  - `test_load_from_dict_missing_criteria_key` — `ValidationError` を raise
  - `test_load_from_s3_success` — `moto` で S3 をモック、正常 JSON を返す
  - `test_load_from_s3_key_not_found` — `moto` で `NoSuchKey` → `CriteriaLoadError`
  - `test_load_from_s3_invalid_json` — 不正 JSON → `CriteriaLoadError`
  - `test_parse_s3_uri_valid` — `s3://bucket/key.json` → `("bucket", "key.json")`
  - `test_parse_s3_uri_invalid` — `ValidationError` を raise
- [X] T021 [P] [US2] `tests/test_handler.py` に US2 テストを追加する
  - `test_openai_provider_selected` — `provider="openai"` → OpenAI が呼ばれる
  - `test_bedrock_provider_selected` — `provider="bedrock"` → Bedrock が呼ばれる
  - `test_criteria_loaded_from_s3` — `criteria_file="s3://b/k.json"` → S3 から読み込まれる
  - `test_invalid_s3_uri_raises_validation_error` — 不正 URI → `ValidationError`

### US2 実装

- [X] T022 [P] [US2] `src/providers/openai.py` を実装する（移植元: `infrastructure/clients/openai_client.py`）
  - 同期 `openai.OpenAI` クライアント（`max_retries=3`, `timeout=config.request_timeout`）
  - `# Cold-start: OpenAI client initialized once per container` コメント付きキャッシュ
  - `complete(messages, model, timeout) -> str`
  - 例外マッピング: `openai.AuthenticationError` / `RateLimitError` / `APIError` → `ProviderError`
- [X] T023 [P] [US2] `src/providers/bedrock.py` を実装する（移植元: `infrastructure/clients/bedrock_client.py`）
  - 同期 `boto3.client("bedrock-runtime")` — IAM 認証（Lambda 実行ロール）を使用
  - `# Cold-start: Bedrock client initialized once per container` コメント付きキャッシュ
  - `complete(messages, model, timeout) -> str` — `converse` API を使用
  - 例外マッピング: `botocore.exceptions.ClientError` → `ProviderError`
- [X] T024 [US2] `src/criteria.py` に S3 ロード機能を追加する
  - `_s3_client = boto3.client("s3")` モジュールレベルキャッシュ（コールドスタートコメント付き）
  - `_parse_s3_uri(s3_uri: str) -> tuple[str, str]` — 不正 URI → `ValidationError`
  - `load_from_s3(s3_uri: str) -> EvaluationCriteria`
    - `ClientError` の error code 分岐: `NoSuchKey` → `CriteriaLoadError`, `AccessDenied` → `ConfigurationError`
    - `json.JSONDecodeError` → `CriteriaLoadError`
    - `logger.info("Criteria loaded from S3", extra={"s3_uri": s3_uri, "criteria_count": ...})`
- [X] T025 [US2] `src/handler.py` の `lambda_handler` を更新する（S3 criteria + マルチプロバイダー対応）
  - `criteria_file` 指定時 → `load_from_s3(criteria_file)` 呼び出し
  - `provider` フィールドのバリデーション（`"anthropic"`, `"openai"`, `"bedrock"` 以外 → `ValidationError`）
  - `src/providers/__init__.py` の `get_provider()` 経由で全プロバイダーに対応

**Checkpoint**: `pytest tests/` が全パス（moto + unittest.mock で実 API 呼び出しなし）

---

## Phase 5: User Story 3 — CDK デプロイ + デプロイスクリプト (P3)

**Goal**: `cdk synth` が成功し、`scripts/deploy.sh` でデプロイが実行できる

**Acceptance Criteria**: AC8（cdk synth 成功）, AC9（deploy.sh 実行可能）

**Independent Test**: `cd cdk && cdk synth LlmJudgeStack` でエラーなし

### US3 実装

- [X] T026 [P] [US3] `cdk/app.py` を作成する
  - `#!/usr/bin/env python3`
  - `cdk.App()` → `LlmJudgeStack` インスタンス化
  - `app.synth()`
  - モジュール docstring（スタック構成の概要）
- [X] T027 [US3] `cdk/stack.py` を実装する（`LlmJudgeStack`）
  - `lambda_.Function` — Python 3.12, handler=`handler.lambda_handler`, 512MB, 60s
  - `lambda_.Code.from_asset("..", bundling=BundlingOptions(...))` — `src/` を asset としてパッケージング
  - 環境変数: `DEFAULT_PROVIDER`, `AWS_REGION`, `LOG_LEVEL`, `POWERTOOLS_SERVICE_NAME`
  - IAM ポリシー: `bedrock:InvokeModel` (`arn:aws:bedrock:*::foundation-model/*`)
  - IAM ポリシー: `s3:GetObject` (context `criteria_bucket_arn` が設定されている場合のみ)
  - `cdk.CfnOutput` で Lambda ARN を出力
  - クラス・メソッドに Google スタイル docstring を記述
- [X] T028 [US3] `scripts/deploy.sh` を実装する
  ```
  Usage: ./scripts/deploy.sh [--env dev|prod] [--region REGION]
  ```
  - `set -euo pipefail`
  - AWS 認証確認（`aws sts get-caller-identity`）
  - `pip install -r cdk/requirements.txt`
  - CDK bootstrap（冪等: 失敗を無視）
  - `cdk deploy LlmJudgeStack --require-approval never`
  - Lambda ARN を標準出力
  - `chmod +x` 実行権限を付与

**Checkpoint**: `cd cdk && pip install -r requirements.txt && cdk synth LlmJudgeStack` がエラーなし

---

## Phase 6: Polish — 品質・ドキュメント整備

**Purpose**: テスト網羅率確認・ドキュメント更新・最終品質チェック

- [X] T029 [P] `pytest --cov=src --cov-report=term-missing` を実行して全テストがパスすることを確認する
- [X] T030 [P] `cdk synth LlmJudgeStack` を実行してエラーがないことを確認する
- [X] T031 [P] `README.md` を更新する（Lambda ハンドラー仕様・デプロイ手順・環境変数一覧）
- [X] T032 型ヒントの一貫性を確認する（`str | None` 形式、Python 3.12 スタイル）
- [X] T033 全ファイルの docstring を確認する（モジュール・クラス・関数に Google スタイルが揃っているか）
- [X] T034 `src/providers/__init__.py` の `get_provider()` が未知のプロバイダー名で `ConfigurationError` を raise することをテストに追加する

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    └─→ Phase 2 (Foundational) ─→ Phase 3 (US1) ─→ Phase 6 (Polish)
                                ─→ Phase 4 (US2) ─→
                                ─→ Phase 5 (US3) ─→
```

- **Phase 1**: 依存なし。即座に着手可能
- **Phase 2**: Phase 1 完了後。US1〜US3 全てをブロック
- **Phase 3 (US1)**: Phase 2 完了後に着手可能
- **Phase 4 (US2)**: Phase 2 完了後に着手可能（US1 と並列実行可）
- **Phase 5 (US3)**: Phase 2 完了後に着手可能（US1/US2 と並列実行可）
- **Phase 6**: Phase 3・4・5 全て完了後

### User Story Dependencies

- **US1**: Phase 2 完了後、即着手可能
- **US2**: Phase 2 完了後、即着手可能（US1 と並列可）
- **US3**: Phase 2 完了後、即着手可能（US1/US2 と並列可）

### Within Each User Story

- テストタスク（[P]）→ 実装タスクの順
- 基盤モジュール（config, criteria, providers/__init__）→ 具体プロバイダー → evaluator → handler

---

## Parallel Opportunities

### Phase 2 内の並列タスク

```bash
# 並列実行可能（別ファイル、依存なし）
T009: src/config.py
T010: src/criteria.py
T011: src/providers/__init__.py
# T008 (handler.py 例外定義) は先に完了する必要あり
```

### Phase 3 内の並列タスク

```bash
# テスト（全て[P]）を先に並列作成
T012: tests/conftest.py
T013: tests/test_handler.py
T014: tests/test_evaluator.py
T015: tests/test_providers.py (Anthropic部分)

# 実装（T016, T017 は並列可）
T016: src/providers/anthropic.py  ←─ 並列
T017: src/evaluator.py            ←─ 並列
T018: src/handler.py lambda_handler 本体（T016, T017 完了後）
```

### Phase 4 内の並列タスク

```bash
# テスト（全て[P]）
T019: tests/test_providers.py (OpenAI, Bedrock部分)
T020: tests/test_criteria.py
T021: tests/test_handler.py (US2追加分)

# 実装
T022: src/providers/openai.py  ←─ 並列
T023: src/providers/bedrock.py ←─ 並列
T024: src/criteria.py S3追加分（T022, T023 に依存しない）
T025: src/handler.py 更新（T022, T023, T024 完了後）
```

### Phase 5 内の並列タスク

```bash
T026: cdk/app.py      ←─ 並列
T028: scripts/deploy.sh ←─ 並列
T027: cdk/stack.py（T026 完了後）
```

---

## Implementation Strategy

### MVP（US1 のみ）

1. Phase 1 (Setup) 完了
2. Phase 2 (Foundational) 完了
3. Phase 3 (US1: Anthropic + デフォルト基準) 完了
4. **停止・検証**: `pytest tests/test_handler.py tests/test_evaluator.py` が全パス
5. Lambda の動作確認（手動テストイベント）

### Incremental Delivery

1. Setup + Foundational → 基盤完成
2. US1 完了 → Anthropic で基本評価が動く（MVP！）
3. US2 完了 → 全プロバイダー + S3 criteria 対応
4. US3 完了 → CDK デプロイ可能
5. Polish → 品質確認

---

## Notes

- `[P]` タスクは異なるファイルを対象とし、相互依存なし
- Lambda はステートレス: ファイル書き込み禁止、`/tmp` 以外の書き込みは避ける
- 全例外は `raise`（`return {"error": ...}` パターン禁止）
- コールドスタート最適化: モジュールレベルのキャッシュ変数には必ず `# Cold-start:` コメントを付ける
- docstring は Google スタイル（Args / Returns / Raises）を全関数に適用
- ライブラリバージョンはこのファイル冒頭の最新版を使用すること
