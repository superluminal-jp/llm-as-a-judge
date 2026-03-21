# llm-as-a-judge Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-21

## Active Technologies
- JSON (static data file — no Python changes) + `src/criteria.py`（`EvaluationCriteria`・`CriterionDefinition` スキーマ、`load_from_s3()`） (003-aisi-safety-criteria)
- `criteria/` ディレクトリ（開発環境）、S3（本番環境 — 既存のS3ローダー経由） (003-aisi-safety-criteria)

- (001-lambda-minimal-restructure)

## Project Structure

```text
src/
tests/
```

## Commands

# Add commands for 

## Code Style

: Follow standard conventions

## Recent Changes
- 003-aisi-safety-criteria: Added JSON (static data file — no Python changes) + `src/criteria.py`（`EvaluationCriteria`・`CriterionDefinition` スキーマ、`load_from_s3()`）

- 001-lambda-minimal-restructure: Added

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
