# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- `config/parameters.json` (and `parameters.example.json`) — deployment/CDK parameters (`aws_region`, `environment`, `default_provider`, `criteria_bucket_arn`); read by `cdk/app.py` and `scripts/deploy.sh` (region when `AWS_REGION` unset)
- `evaluation_steps` field on `CriterionDefinition` — ordered list of yes/no questions the judge LLM works through before scoring
- `criterion_reasoning` field in Lambda response — per-criterion reasoning text (includes numbered step answers when `evaluation_steps` defined)
- `examples/` directory with I/O samples for `default.json` and `disclosure_evaluation_criteria.json` criteria
- `criteria/disclosure_evaluation_criteria.json` — 情報公開法第 5 条第 1〜6 号の不開示事由評価基準（6 クライテリア、段階的推論付き）

### Fixed

- `BEDROCK_MODEL` default changed to `jp.anthropic.claude-sonnet-4-6` (JP cross-region inference profile for ap-northeast-1/ap-northeast-3); previously `anthropic.claude-sonnet-4-6` required an inference profile ARN
- `BedrockProvider.complete` now retries up to 3 times with exponential backoff for `ThrottlingException` and `AccessDeniedException` (transient failures from cross-region routing under parallel load) — Claude models require a cross-region inference profile ARN in ap-northeast-1 and cannot be invoked with on-demand throughput directly

### Changed

- `README.md`: removed license badge and「ライセンス」節; removed root `LICENSE` — リポジトリ内ではライセンスを明示しない
- `reasoning` field is now an LLM-generated executive summary (総評) synthesising all per-criterion findings, replacing the previous score-list string; one additional LLM call is made after parallel criterion evaluation
- Prompt builder includes numbered evaluation steps and requests `step_reasoning` JSON array when `evaluation_steps` are defined
- Response parser embeds `step_reasoning` into `criterion_reasoning` as `Step N: … \n\nFinal: …` format
- `_aggregate_parallel_results` now populates `criterion_reasoning` dict (previously discarded per-criterion reasoning)
- `disclosure_evaluation_criteria.json` restructured to match `default.json` schema: `id`→`name`, nested `score_descriptors`→flat strings, metadata fields→`evaluation_prompt`/`description`
- `default.json` updated with `evaluation_steps` (3 steps per criterion) across all 7 criteria
- README.md rewritten in Japanese with updated response schema and `evaluation_steps` documentation
- `criteria/README.md` rewritten in Japanese reflecting actual file listing
- Updated `contracts/criteria-file.json` schema to include `evaluation_steps` property
- Updated `contracts/lambda-response.json` schema to include `criterion_reasoning` property
- Test count: 58 → 56 (criteria tests updated for new fields)
- Documentation: README badge and test section (94 tests, ~88% `src/` coverage), deploy prerequisites (Docker required for bundling), CDK stack notes; `criteria/README.md` runtime criteria loading clarified
- Documentation: added `docs/` (index, architecture, development, troubleshooting, JSON schema pointers), `docs/quickstart.md`, `docs/repository-layout.md`; expanded `config/README.md` (precedence, `parameters.local.json`)
- `cdk/app.py` and `scripts/deploy.sh`: merge `config/parameters.local.json` over `parameters.json` (same keys) when present

### Removed

- Version control for AI/editor tooling directories: `.claude/`, `.cursor/`, `.specify/` removed from the Git index; `.gitignore` now excludes those plus `.speckit/`, `.agents/`, `.codex/` (files remain locally)
- `specs/` excluded from Git; canonical JSON Schemas in repository root [`contracts/`](contracts/) (`lambda-event.json`, `lambda-response.json`, `criteria-file.json`)
- `CLAUDE.md` excluded from Git (local agent notes only)
- Per-directory READMEs under `src/`, `tests/`, `scripts/`, `cdk/`, `contracts/` removed; content merged into [`docs/repository-layout.md`](docs/repository-layout.md)
- Local evaluation CLI (`src/cli.py`, `python -m src.cli`) — invoke the deployed Lambda or run tests instead
- `load_from_file()` in `src/criteria.py` — criteria loaded at runtime via S3 (`load_from_s3`) or `DefaultCriteria.balanced()` only
- CDK `_LocalBundler` / `ILocalBundling` — Lambda asset bundling uses Docker only (`cdk synth` / `cdk deploy` require a running Docker daemon)
- `criteria/administrative_information_non_disclosure.json` — replaced by `disclosure_evaluation_criteria.json`
- `criteria/template.json` — removed (redundant with README examples)

### Changed (prior)

- Refactored from DDD + CLI architecture (60+ files) to AWS Lambda minimal flat structure (~8 source files)
- Replaced asyncio-based clients with synchronous SDK calls
- Replaced DDD exception hierarchy with a flat `LlmJudgeError` hierarchy in `src/handler.py`
- Default Bedrock model changed to `amazon.nova-lite-v1:0` (available in all regions)

### Added

- `src/handler.py` — synchronous Lambda entry point with `@logger.inject_lambda_context`
- `src/evaluator.py` — multi-criteria prompt builder, LLM call orchestrator, JSON parser
- `src/criteria.py` — `EvaluationCriteria` dataclass, S3 JSON loader, `DefaultCriteria.balanced()`
- `src/config.py` — frozen `Config` dataclass with cold-start environment-variable caching
- `src/providers/` — `BaseProvider` protocol, `AnthropicProvider`, `OpenAIProvider`, `BedrockProvider`
- `tests/` — 58 tests (92% coverage) using `pytest` + `unittest.mock` + `moto[s3]`; no real API calls
- `cdk/` — `LlmJudgeStack` CDK v2 stack (Python 3.12, 512 MB, 60 s timeout, Bedrock IAM)
- `scripts/deploy.sh` — CDK bootstrap + deploy wrapper with AWS auth check
- `requirements.txt`, `requirements-dev.txt`, `cdk/requirements.txt`
- `specs/001-lambda-minimal-restructure/` — spec-kit artifacts (spec, plan, tasks, data-model, contracts)

### Removed

- `src/llm_judge/` — DDD package (domain, application, infrastructure, presentation layers)
- `tests/unit/`, `tests/integration/` — replaced by new flat test suite
- `docs/` — DDD architecture docs (superseded by README)
- `test_samples/`, `config.json`, `setup.py`, `.env.example` — CLI artifacts
