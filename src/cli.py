"""Command-line interface for local LLM-as-a-Judge evaluation.

Runs the same evaluation pipeline as the Lambda handler, but reads input from
CLI arguments/files and prints the result as JSON to stdout.

Usage::

    python -m src.cli --prompt "Q?" --response "A." [options]

Options:
    --prompt TEXT          Original prompt/question (required unless --prompt-file)
    --prompt-file PATH     Read prompt from a text file
    --response TEXT        LLM response to evaluate (required unless --response-file)
    --response-file PATH   Read response from a text file
    --provider NAME        Provider: anthropic, openai, bedrock
                           (default: DEFAULT_PROVIDER env var, or "anthropic")
    --model NAME           Judge model (default: provider default)
    --criteria PATH        Local criteria JSON file path
                           (default: DefaultCriteria.balanced())
    --timeout SEC          Request timeout in seconds (default: 30)
    --indent N             JSON output indent width (default: 2, 0 = compact)

Environment Variables:
    DEFAULT_PROVIDER       Default provider when --provider is omitted
    ANTHROPIC_API_KEY      Required when provider is anthropic
    OPENAI_API_KEY         Required when provider is openai
    AWS credentials        Required when provider is bedrock

Example::

    export ANTHROPIC_API_KEY=sk-ant-...
    python -m src.cli \\
        --provider anthropic \\
        --prompt "機械学習とは何ですか？" \\
        --response "機械学習はデータからパターンを学習する技術です。" \\
        --criteria criteria/default.json
"""

from __future__ import annotations

import argparse
import json
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="LLM-as-a-Judge: evaluate an LLM response locally.",
    )

    input_group = parser.add_argument_group("input")
    prompt_mx = input_group.add_mutually_exclusive_group(required=True)
    prompt_mx.add_argument("--prompt", metavar="TEXT", help="Original prompt text")
    prompt_mx.add_argument(
        "--prompt-file", metavar="PATH", help="Read prompt from a text file"
    )
    response_mx = input_group.add_mutually_exclusive_group(required=True)
    response_mx.add_argument("--response", metavar="TEXT", help="LLM response text")
    response_mx.add_argument(
        "--response-file", metavar="PATH", help="Read response from a text file"
    )

    model_group = parser.add_argument_group("model")
    model_group.add_argument(
        "--provider",
        choices=["anthropic", "openai", "bedrock"],
        metavar="NAME",
        help="LLM provider (anthropic / openai / bedrock)",
    )
    model_group.add_argument(
        "--model", metavar="NAME", help="Judge model name/ID (uses provider default if omitted)"
    )

    criteria_group = parser.add_argument_group("criteria")
    criteria_group.add_argument(
        "--criteria",
        metavar="PATH",
        help="Local criteria JSON file (uses DefaultCriteria.balanced() if omitted)",
    )

    misc_group = parser.add_argument_group("misc")
    misc_group.add_argument(
        "--timeout", type=int, default=30, metavar="SEC", help="Request timeout in seconds (default: 30)"
    )
    misc_group.add_argument(
        "--indent", type=int, default=2, metavar="N", help="JSON output indent (default: 2, 0=compact)"
    )

    return parser


def _read_text(arg: str | None, file_arg: str | None, label: str) -> str:
    if arg is not None:
        return arg
    try:
        with open(file_arg, encoding="utf-8") as f:  # type: ignore[arg-type]
            return f.read()
    except FileNotFoundError:
        print(f"Error: {label} file not found: {file_arg}", file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print(f"Error: cannot read {label} file: {exc}", file=sys.stderr)
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    from src.config import get_config, validate_for_provider
    from src.criteria import DefaultCriteria, load_from_file
    from src.evaluator import evaluate
    from src.handler import (
        ConfigurationError,
        CriteriaLoadError,
        ProviderError,
        ValidationError,
    )
    from src.providers import get_provider

    prompt = _read_text(args.prompt, args.prompt_file, "prompt")
    response = _read_text(args.response, args.response_file, "response")

    config = get_config()

    provider_name: str = args.provider or config.default_provider or "anthropic"

    try:
        validate_for_provider(config, provider_name)
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    judge_model: str = args.model or _default_model(config, provider_name)

    if args.criteria:
        try:
            criteria = load_from_file(args.criteria)
        except (CriteriaLoadError, ValidationError) as exc:
            print(f"Criteria error: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        criteria = DefaultCriteria.balanced()

    try:
        provider = get_provider(provider_name, config)
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        result = evaluate(
            prompt=prompt,
            response=response,
            criteria=criteria,
            provider=provider,
            model=judge_model,
            timeout=args.timeout,
            provider_name=provider_name,
        )
    except ProviderError as exc:
        print(f"Provider error: {exc}", file=sys.stderr)
        sys.exit(1)

    indent = args.indent if args.indent > 0 else None
    print(json.dumps(result, ensure_ascii=False, indent=indent))


def _default_model(config, provider_name: str) -> str:
    mapping = {
        "anthropic": config.anthropic_model,
        "openai": config.openai_model,
        "bedrock": config.bedrock_model,
    }
    return mapping.get(provider_name, "")


if __name__ == "__main__":
    main()
