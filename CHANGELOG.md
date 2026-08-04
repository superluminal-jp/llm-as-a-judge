# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- **Asynchronous workflow.** The stack now deploys two state machines from one definition: Express for synchronous `StartSyncExecution`, and Standard with a Distributed Map for large criteria sets and bulk submission. Express caps an execution at 5 minutes and an inline Map at 40 concurrent iterations; Standard has neither ceiling. Asynchronous callers collect the result from `final/<content-hash>.json` in the jobs bucket
- **Idempotency for judge calls** (`src/idempotency.py`, DynamoDB table with TTL). Keyed on a content hash of the evaluation inputs plus criterion and model — not the job URI, which is unique per execution and would never match. Two identical submissions deduplicate; changing the prompt, criteria, or model does not. With `IDEMPOTENCY_TABLE` unset the decorator is a pass-through, so local runs and tests need no DynamoDB
- **Per-criterion result offloading.** Reasoning text goes to S3 under a deterministic key and only a pointer crosses the state boundary, so state size no longer scales with the criteria count. `summarize` fetches them back concurrently
- `src/errors.py` and `src/validation.py`, carrying the exception hierarchy and event validation that used to sit in `src/handler.py`

### Added (earlier in this release)

- **Step Functions Express workflow** as a second entry point alongside the direct-invoke Lambda: `Prepare → Map(MaxConcurrency)[EvaluateCriterion] → Summarize`. Per-criterion retry with backoff and FULL jitter is declared on the Map state, so a throttled criterion no longer blocks in `time.sleep` on billed Lambda time. Both entry points accept identical events and return identical responses (asserted by `tests/test_workflow_handlers.py::TestWorkflowMatchesDirectInvoke`)
- `src/handlers/{prepare,evaluate_criterion,summarize}.py` — workflow steps, each reusing the existing prompt/parse/aggregate functions in `src/evaluator.py` rather than reimplementing them
- `src/jobs.py` — claim-check payload staging in S3, working around the 256 KB Step Functions inter-state data limit; container-level cache so parallel Map branches do not each re-read the object
- `src/observability.py` — shared Powertools `Tracer` and `Metrics`; EMF metrics `EvaluationsCompleted`, `EvaluationsFailed`, `CriterionEvaluationFailed`, `NotAssessableCount`, `BedrockThrottled`, `JudgeLatencyMs`
- Secrets Manager secret for Anthropic/OpenAI API keys, resolved lazily by `src.config.get_api_key`; keys are no longer expected in Lambda environment variables
- Customer-managed KMS key encrypting the function environment, secret, DLQ, and alarm topic
- SQS dead-letter queue for failed asynchronous invocations
- CloudWatch alarms (errors, throttles, p99 duration, DLQ depth, workflow failures) notifying an SNS topic, plus a dashboard
- Stack-managed criteria bucket (encrypted, versioned, TLS-only, public access blocked, server access logging) created when `criteria_bucket_arn` is empty
- cdk-nag AWS Solutions rule pack on every synth; `tests/test_cdk_stack.py` fails the build on any unsuppressed finding
- `tests/test_cdk_stack.py`, `tests/test_config.py`, `tests/test_observability.py`, `tests/test_workflow_handlers.py` — test count 105 → 201, all runnable without Docker
- `config/parameters.json` keys `bedrock_model`, `bedrock_allowed_models`, `bedrock_inference_profile_regions`, which drive the Bedrock IAM policy
- `TARGET=workflow` mode in `scripts/lambda_pattern_tests.py`, running the same cases against the state machine

- `config/parameters.json` (and `parameters.example.json`) — deployment/CDK parameters (`aws_region`, `environment`, `default_provider`, `criteria_bucket_arn`); read by `cdk/app.py` and `scripts/deploy.sh` (region when `AWS_REGION` unset)
- `evaluation_steps` field on `CriterionDefinition` — ordered list of yes/no questions the judge LLM works through before scoring
- `criterion_reasoning` field in Lambda response — per-criterion reasoning text (includes numbered step answers when `evaluation_steps` defined)
- `examples/` directory with I/O samples for `default.json` and `disclosure_evaluation_criteria.json` criteria
- `criteria/disclosure_evaluation_criteria.json` — 情報公開法第 5 条第 1〜6 号の不開示事由評価基準（6 クライテリア、段階的推論付き）

### Fixed

- Two more least-privilege gaps the CDK tests caught: `jobs_bucket.grant_read` was handing the criterion worker bucket-level `s3:List*` and `s3:GetBucket*` when every access it makes is by a known key, and only the criterion worker should reach the idempotency table. Both are now written out as object-level or step-scoped grants

### Fixed (earlier in this release)

- **Bedrock IAM did not permit the default model.** `BEDROCK_MODEL` defaults to `jp.anthropic.claude-sonnet-4-6`, a cross-region inference profile ID, but the stack granted `bedrock:InvokeModel` only on `arn:aws:bedrock:*::foundation-model/*`. Invoking through an inference profile also requires the grant on the inference profile ARN and on the underlying foundation model in every routed region, so the default configuration failed with `AccessDeniedException`. The policy is now built from `bedrock_allowed_models` and `bedrock_inference_profile_regions` and emits both ARN forms — and, being model-specific, no longer grants every foundation model in every region
- **`REQUEST_TIMEOUT` had no effect on Bedrock.** `BedrockProvider` built its boto3 client without a `botocore.config.Config`, so botocore's 60-second default read timeout applied — identical to the then-current Lambda timeout, meaning the function was killed before its own timeout could report anything useful. Socket timeouts now derive from `REQUEST_TIMEOUT`, and the Lambda timeout moved to 300 s
- **Connection pool throttled large criteria files.** `ThreadPoolExecutor` was sized at `len(criteria)`, so the 10-criterion AISI file opened 10 concurrent calls against botocore's default 10-connection pool. Fan-out became `min(len(criteria), MAX_PARALLEL_CRITERIA)`, and then moved out of the process entirely when the Map state took over concurrency
- CloudWatch log groups are now created explicitly with bounded retention; previously the Lambda service created them lazily with "Never expire"
- The execution role now holds `kms:GenerateDataKey`, without which delivery to the KMS-encrypted DLQ would fail silently, and CloudWatch holds key access, without which alarm notifications to the encrypted SNS topic would be dropped
- Criteria bucket server access logging enabled — reads and changes to the files defining how submissions are scored previously left no audit trail


- `BEDROCK_MODEL` default changed to `jp.anthropic.claude-sonnet-4-6` (JP cross-region inference profile for ap-northeast-1/ap-northeast-3); previously `anthropic.claude-sonnet-4-6` required an inference profile ARN

### Changed

- **The single-Lambda evaluation path is removed.** `src/handler.py` and `evaluator.evaluate()` are gone, along with the thread-pool fan-out. Keeping a second implementation of the same contract meant verifying every change twice, and the thread pool could not scale in either direction the service is heading. The workflow is the only entry point
- `evaluator.py` keeps only the pure building blocks the workflow steps compose; `_build_summary_prompt` and `_aggregate_parallel_results` become `build_summary_prompt` and `aggregate_results` now that they cross a module boundary
- `scripts/lambda_pattern_tests.py` becomes `scripts/workflow_pattern_tests.py`, with `TARGET=sync|async` replacing `TARGET=lambda|workflow`
- `tests/test_handler.py` becomes `tests/test_validation.py`, calling the validation functions directly rather than mocking a provider and evaluator to assert a malformed field is rejected. The direct-invoke equivalence test becomes a contract test validating the response against `contracts/lambda-response.json`
- DynamoDB point-in-time recovery uses `PointInTimeRecoverySpecification`; the flat property is deprecated
- `MAX_PARALLEL_CRITERIA` is removed. With one criterion per invocation it no longer bounded anything, and a knob that does not do what its name says is the failure mode this release exists to fix. Concurrency is the Map state's `MaxConcurrency`

### Changed (earlier in this release)

- **`BedrockProvider` no longer retries by hand.** The previous loop blocked in `time.sleep` on billed Lambda time and treated `AccessDeniedException` as transient — it is not, and retrying it merely delayed the failure while masking the IAM gap fixed above. Retries are now botocore's, in `adaptive` mode, which adds client-side rate limiting suited to Bedrock throttling. `AccessDeniedException` fails immediately with a message naming the two grants a cross-region profile needs
- Lambda runtime Python 3.12 → 3.13, on ARM64/Graviton; reserved concurrency set
- Stacks are named `LlmJudgeStack-<environment>` and deploy into an explicit account/region, so `aws_region` and `environment` in `config/parameters.json` are wired through instead of being read and discarded
- `scripts/deploy.sh` no longer bootstraps on every run (`--bootstrap` is now explicit) and bootstraps with policies scoped to the services this stack creates rather than `AdministratorAccess`
- Per-criterion failure remains fail-fast, now with a `CriterionEvaluationFailed` metric and the criterion name in logs. A criterion that could not be scored is deliberately not folded into `not_assessable`: doing so would understate the rubric while returning a response that looks complete
- `config/parameters.json` no longer contains a real AWS account ID; account-specific values belong in the gitignored `parameters.local.json`
- The Lambda asset excludes docs, tests, and scripts, so editing them no longer changes the asset hash and forces a redeploy


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
- `cdk/` — `LlmJudgeStack-<env>` CDK v2 stack (4 Lambdas on Python 3.13/ARM64, Step Functions Express workflow, IAM/KMS/S3/SQS/CloudWatch)
- `scripts/deploy.sh` — CDK bootstrap + deploy wrapper with AWS auth check
- `requirements.txt`, `requirements-dev.txt`, `cdk/requirements.txt`
- `specs/001-lambda-minimal-restructure/` — spec-kit artifacts (spec, plan, tasks, data-model, contracts)

### Removed

- `src/llm_judge/` — DDD package (domain, application, infrastructure, presentation layers)
- `tests/unit/`, `tests/integration/` — replaced by new flat test suite
- `docs/` — DDD architecture docs (superseded by README)
- `test_samples/`, `config.json`, `setup.py`, `.env.example` — CLI artifacts
