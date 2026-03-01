# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Changed

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
