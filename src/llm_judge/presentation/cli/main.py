#!/usr/bin/env python3
"""
LLM-as-a-Judge CLI Interface

Provides command-line access to evaluation and comparison functionality.
"""

import argparse
import asyncio
import json
import sys
from typing import Dict, Any, Optional
from pathlib import Path

from ...application.services.llm_judge_service import (
    LLMJudge,
    CandidateResponse,
    EvaluationResult,
)
from ...infrastructure.config.config import LLMConfig, load_config
from ...domain.evaluation.criteria import DefaultCriteria
from ...domain.evaluation.weight_config import WeightConfigParser, CriteriaWeightApplier
from ...domain.evaluation.custom_criteria import (
    CustomCriteriaParser,
    CustomCriteriaBuilder,
    get_available_criterion_types,
    save_criteria_template,
    create_criteria_template,
)
from ...infrastructure.persistence.persistence_service import PersistenceServiceImpl
from ...domain.persistence.models import PersistenceConfig
from .batch_commands import add_batch_commands
from .multi_criteria_display import MultiCriteriaDisplayFormatter


class CLIError(Exception):
    """CLI-specific error for user-friendly error handling."""

    pass


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser."""
    parser = argparse.ArgumentParser(
        prog="llm-judge",
        description="LLM-as-a-Judge: Evaluate and compare language model responses",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Evaluate a single response (uses comprehensive criteria by default)
  llm-judge evaluate "What is AI?" "AI is artificial intelligence"
  
  # Use specific criteria type
  llm-judge evaluate "What is AI?" "AI is artificial intelligence" --criteria-type basic
  
  # Use technical criteria for technical content
  llm-judge evaluate "Explain ML" "Machine learning is..." --criteria-type technical
  
  # Use custom criteria weights
  llm-judge evaluate "What is AI?" "AI is artificial intelligence" --criteria-weights "accuracy:0.4,clarity:0.3,helpfulness:0.3"
  
  # Use equal weights for all criteria
  llm-judge evaluate "What is AI?" "AI is artificial intelligence" --equal-weights
  
  # Use custom criteria definition
  llm-judge evaluate "What is AI?" "AI is artificial intelligence" --custom-criteria "accuracy:Factual correctness:factual:0.4,clarity:How clear the response is:linguistic:0.3"
  
  # Use criteria from file
  llm-judge evaluate "What is AI?" "AI is artificial intelligence" --criteria-file ./my-criteria.json
  
  # List available criteria types
  llm-judge evaluate --list-criteria-types
  
  # Create criteria template
  llm-judge create-criteria-template my-criteria.json --name "Academic Evaluation" --description "Criteria for academic content"
  
  # Compare two responses
  llm-judge compare "Explain ML" "Basic explanation" "Detailed explanation" --model-a gpt-4 --model-b claude-3
  
  # Use specific provider and model
  llm-judge evaluate "Question" "Answer" --provider openai --judge-model gpt-4
  
  # Use configuration file
  llm-judge evaluate "Question" "Answer" --config ./my-config.json
  
  # Output as JSON
  llm-judge evaluate "Question" "Answer" --output json
        """,
    )

    # Global options
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic", "bedrock"],
        help="LLM provider to use as judge",
    )
    parser.add_argument("--judge-model", help="Specific model to use as judge")
    parser.add_argument("--config", type=Path, help="Path to configuration file")
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Evaluate command
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate a single response")
    eval_parser.add_argument("prompt", nargs="?", help="The prompt/question")
    eval_parser.add_argument("response", nargs="?", help="The response to evaluate")
    eval_parser.add_argument(
        "--criteria",
        default="overall quality",
        help='Evaluation criteria (default: "overall quality")',
    )
    eval_parser.add_argument("--model", help="Model that generated the response")
    eval_parser.add_argument(
        "--criteria-type",
        choices=["comprehensive", "basic", "technical", "creative"],
        help="Type of default criteria to use (overrides config)",
    )
    eval_parser.add_argument(
        "--show-detailed",
        action="store_true",
        help="Show detailed multi-criteria breakdown",
    )
    eval_parser.add_argument(
        "--criteria-weights",
        type=str,
        help="Custom criteria weights in format 'criterion1:weight1,criterion2:weight2' (e.g., 'accuracy:0.3,clarity:0.2,helpfulness:0.5')",
    )
    eval_parser.add_argument(
        "--equal-weights",
        action="store_true",
        help="Use equal weights for all criteria (overrides default weights)",
    )
    eval_parser.add_argument(
        "--custom-criteria",
        type=str,
        help="Custom criteria definition in format 'name:description:type:weight,name2:description2:type2:weight2' (e.g., 'accuracy:Factual correctness:factual:0.4,clarity:How clear the response is:linguistic:0.3')",
    )
    eval_parser.add_argument(
        "--criteria-file",
        type=Path,
        help="Path to JSON file containing custom criteria definitions",
    )
    eval_parser.add_argument(
        "--list-criteria-types",
        action="store_true",
        help="List available criteria types and exit",
    )

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two responses")
    compare_parser.add_argument("prompt", help="The prompt/question")
    compare_parser.add_argument("response_a", help="First response to compare")
    compare_parser.add_argument("response_b", help="Second response to compare")
    compare_parser.add_argument("--model-a", help="Model that generated response A")
    compare_parser.add_argument("--model-b", help="Model that generated response B")

    # Add batch commands
    add_batch_commands(subparsers)

    # Add criteria template command
    template_parser = subparsers.add_parser(
        "create-criteria-template", help="Create a criteria template file"
    )
    template_parser.add_argument(
        "output_file", type=Path, help="Output file path for the template"
    )
    template_parser.add_argument(
        "--name",
        default="Custom Evaluation Criteria",
        help="Name for the criteria set (default: 'Custom Evaluation Criteria')",
    )
    template_parser.add_argument(
        "--description",
        default="Custom evaluation criteria for specific use case",
        help="Description for the criteria set",
    )

    # Add data management commands
    data_parser = subparsers.add_parser(
        "data", help="Data persistence management commands"
    )
    data_subparsers = data_parser.add_subparsers(
        dest="data_command", help="Data management subcommands"
    )

    # List evaluations command
    list_parser = data_subparsers.add_parser(
        "list", help="List stored evaluation results"
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of results to display (default: 10)",
    )
    list_parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )

    # Export evaluations command
    export_parser = data_subparsers.add_parser(
        "export", help="Export evaluation results to file"
    )
    export_parser.add_argument(
        "output_file", type=Path, help="Output file path (JSON format)"
    )
    export_parser.add_argument(
        "--limit", type=int, help="Maximum number of results to export (default: all)"
    )

    # Clean cache command
    clean_parser = data_subparsers.add_parser(
        "clean-cache", help="Clean evaluation cache"
    )
    clean_parser.add_argument(
        "--force", action="store_true", help="Force cleanup without confirmation"
    )

    return parser


def list_criteria_types():
    """List available criteria types and exit."""
    print("Available Criteria Types:")
    print("=" * 50)

    criterion_types = get_available_criterion_types()
    for criterion_type in criterion_types:
        print(f"  - {criterion_type}")

    print("\nExample Usage:")
    print(
        "  --custom-criteria 'accuracy:Factual correctness:factual:0.4,clarity:How clear the response is:linguistic:0.3'"
    )
    print("  --criteria-file ./my-criteria.json")

    print("\nTo create a criteria template file:")
    print(
        "  python -c \"from src.llm_judge.domain.evaluation.custom_criteria import save_criteria_template; save_criteria_template('template.json')\""
    )


def load_cli_config(
    config_path: Optional[Path], provider: Optional[str], judge_model: Optional[str]
) -> LLMConfig:
    """Load configuration from file or environment with CLI overrides."""
    if config_path:
        if not config_path.exists():
            raise CLIError(f"Configuration file not found: {config_path}")

        try:
            with open(config_path) as f:
                config_data = json.load(f)
            config = LLMConfig(**config_data)
        except Exception as e:
            raise CLIError(f"Error loading configuration: {e}")
    else:
        config = load_config()

    # Override with CLI arguments
    if provider:
        config.default_provider = provider

    return config


async def evaluate_command(args: argparse.Namespace) -> Dict[str, Any]:
    """Execute the evaluate command."""
    # Check if list-criteria-types is requested
    if hasattr(args, "list_criteria_types") and args.list_criteria_types:
        list_criteria_types()
        return {}

    # Validate required arguments for normal evaluation
    if not args.prompt or not args.response:
        raise CLIError("Both prompt and response are required for evaluation")

    config = load_cli_config(args.config, args.provider, args.judge_model)

    candidate = CandidateResponse(
        prompt=args.prompt, response=args.response, model=args.model or "unknown"
    )

    judge = LLMJudge(config, judge_model=args.judge_model)

    try:
        # Use multi-criteria evaluation with specified criteria type
        criteria_type = getattr(args, "criteria_type", None)

        # Handle custom criteria and weight configuration
        custom_criteria = None

        # Check for custom criteria definition (CLI args override config file)
        custom_criteria_string = (
            getattr(args, "custom_criteria", None) or config.custom_criteria
        )
        criteria_file_path = getattr(args, "criteria_file", None) or (
            Path(config.criteria_file) if config.criteria_file else None
        )

        if custom_criteria_string:
            try:
                criteria_definitions = CustomCriteriaParser.parse_criteria_string(
                    custom_criteria_string
                )
                builder = CustomCriteriaBuilder()
                for cd in criteria_definitions:
                    builder.add_criterion(
                        name=cd.name,
                        description=cd.description,
                        criterion_type=cd.criterion_type,
                        weight=cd.weight,
                        evaluation_prompt=cd.evaluation_prompt,
                        examples=cd.examples,
                        domain_specific=cd.domain_specific,
                        requires_context=cd.requires_context,
                        metadata=cd.metadata,
                    )
                custom_criteria = builder.build(normalize_weights=False)
            except ValueError as e:
                raise CLIError(f"Invalid custom criteria: {e}")

        elif criteria_file_path:
            try:
                criteria_definitions = CustomCriteriaParser.parse_criteria_file(
                    criteria_file_path
                )
                builder = CustomCriteriaBuilder()
                for cd in criteria_definitions:
                    builder.add_criterion(
                        name=cd.name,
                        description=cd.description,
                        criterion_type=cd.criterion_type,
                        weight=cd.weight,
                        evaluation_prompt=cd.evaluation_prompt,
                        examples=cd.examples,
                        domain_specific=cd.domain_specific,
                        requires_context=cd.requires_context,
                        metadata=cd.metadata,
                    )
                custom_criteria = builder.build(normalize_weights=False)
            except (ValueError, FileNotFoundError) as e:
                raise CLIError(f"Error loading criteria file: {e}")

        # Only apply weight configuration if no custom criteria are defined
        if custom_criteria is None:
            # Check for weight configuration from CLI args or config file
            criteria_weights = (
                getattr(args, "criteria_weights", None) or config.criteria_weights
            )
            use_equal_weights = (
                getattr(args, "equal_weights", False) or config.use_equal_weights
            )

            if criteria_weights:
                try:
                    weight_config = WeightConfigParser.parse_weight_string(
                        criteria_weights
                    )
                    # Get base criteria
                    if criteria_type == "comprehensive":
                        base_criteria = DefaultCriteria.comprehensive()
                    elif criteria_type == "basic":
                        base_criteria = DefaultCriteria.basic()
                    elif criteria_type == "technical":
                        base_criteria = DefaultCriteria.technical()
                    elif criteria_type == "creative":
                        base_criteria = DefaultCriteria.creative()
                    else:
                        base_criteria = DefaultCriteria.comprehensive()  # Default

                    custom_criteria = CriteriaWeightApplier.apply_weights(
                        base_criteria, weight_config
                    )
                except ValueError as e:
                    raise CLIError(f"Invalid criteria weights: {e}")

            elif use_equal_weights:
                # Apply equal weights
                if criteria_type == "comprehensive":
                    base_criteria = DefaultCriteria.comprehensive()
                elif criteria_type == "basic":
                    base_criteria = DefaultCriteria.basic()
                elif criteria_type == "technical":
                    base_criteria = DefaultCriteria.technical()
                elif criteria_type == "creative":
                    base_criteria = DefaultCriteria.creative()
                else:
                    base_criteria = DefaultCriteria.comprehensive()  # Default

                criteria_names = [c.name for c in base_criteria.criteria]
                weight_config = WeightConfigParser.create_equal_weights(criteria_names)
                custom_criteria = CriteriaWeightApplier.apply_weights(
                    base_criteria, weight_config
                )

        multi_result = await judge.evaluate_multi_criteria(
            candidate, criteria_type=criteria_type, custom_criteria=custom_criteria
        )
        return {
            "type": "multi_criteria_evaluation",
            "prompt": args.prompt,
            "response": args.response,
            "model": args.model or "unknown",
            "multi_criteria_result": multi_result,
            "judge_model": judge.judge_model,
            "show_detailed": getattr(args, "show_detailed", False),
        }
    finally:
        await judge.close()


async def compare_command(args: argparse.Namespace) -> Dict[str, Any]:
    """Execute the compare command."""
    config = load_cli_config(args.config, args.provider, args.judge_model)

    candidate_a = CandidateResponse(
        prompt=args.prompt, response=args.response_a, model=args.model_a or "unknown"
    )

    candidate_b = CandidateResponse(
        prompt=args.prompt, response=args.response_b, model=args.model_b or "unknown"
    )

    judge = LLMJudge(config, judge_model=args.judge_model)

    try:
        result = await judge.compare_responses(candidate_a, candidate_b)
        return {
            "type": "comparison",
            "prompt": args.prompt,
            "response_a": args.response_a,
            "response_b": args.response_b,
            "model_a": args.model_a or "unknown",
            "model_b": args.model_b or "unknown",
            "winner": result["winner"],
            "reasoning": result["reasoning"],
            "confidence": result.get("confidence", 0.0),
            "judge_model": judge.judge_model,
        }
    finally:
        await judge.close()


def format_evaluation_output(result: Dict[str, Any], output_format: str) -> str:
    """Format evaluation result for display."""
    if output_format == "json":
        return json.dumps(result, indent=2)

    # Text format
    output = []
    output.append("=== LLM-as-a-Judge Evaluation ===")
    output.append(f"Judge Model: {result['judge_model']}")
    output.append(f"Criteria: {result['criteria']}")
    output.append("")
    output.append(f"Prompt: {result['prompt']}")
    output.append(f"Response: {result['response']}")
    output.append(f"Model: {result['model']}")
    output.append("")
    output.append(f"Score: {result['score']}/5")
    output.append(f"Confidence: {result['confidence']:.2f}")
    output.append("")
    output.append("Reasoning:")
    output.append(result["reasoning"])

    return "\n".join(output)


def format_comparison_output(result: Dict[str, Any], output_format: str) -> str:
    """Format comparison result for display."""
    if output_format == "json":
        return json.dumps(result, indent=2)

    # Text format
    output = []
    output.append("=== LLM-as-a-Judge Comparison ===")
    output.append(f"Judge Model: {result['judge_model']}")
    output.append("")
    output.append(f"Prompt: {result['prompt']}")
    output.append("")
    output.append(f"Response A ({result['model_a']}): {result['response_a']}")
    output.append(f"Response B ({result['model_b']}): {result['response_b']}")
    output.append("")

    winner = result["winner"]
    if winner == "tie":
        output.append("Result: TIE")
    else:
        output.append(f"Winner: Response {winner}")

    output.append(f"Confidence: {result['confidence']:.2f}")
    output.append("")
    output.append("Reasoning:")
    output.append(result["reasoning"])

    return "\n".join(output)


async def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "evaluate":
            result = await evaluate_command(args)

            # Handle list-criteria-types case
            if not result:
                return

            if result["type"] == "multi_criteria_evaluation":
                # Use multi-criteria display formatter
                formatter = MultiCriteriaDisplayFormatter()
                output = formatter.format_evaluation_result(
                    result["multi_criteria_result"], args.output
                )
            else:
                # Use legacy single-criterion formatter
                output = format_evaluation_output(result, args.output)

            print(output)
        elif args.command == "compare":
            result = await compare_command(args)
            output = format_comparison_output(result, args.output)
            print(output)
        elif args.command == "create-criteria-template":
            # Handle criteria template creation
            try:
                template = create_criteria_template()
                template["name"] = args.name
                template["description"] = args.description

                with open(args.output_file, "w", encoding="utf-8") as f:
                    json.dump(template, f, indent=2, ensure_ascii=False)

                print(f"Criteria template created: {args.output_file}")
                print(
                    "Edit the file to customize your criteria, then use with --criteria-file"
                )
            except Exception as e:
                raise CLIError(f"Error creating template: {e}")
        elif args.command in ["batch", "create-sample-batch"]:
            # Handle batch commands asynchronously
            exit_code = await args.func(args)
            sys.exit(exit_code)
        elif args.command == "data":
            # Handle data management commands
            if args.data_command == "list":
                await data_list_command(args)
            elif args.data_command == "export":
                await data_export_command(args)
            elif args.data_command == "clean-cache":
                await data_clean_cache_command(args)
            else:
                print(f"Unknown data command: {args.data_command}", file=sys.stderr)
                sys.exit(1)
        else:
            raise CLIError(f"Unknown command: {args.command}")

    except CLIError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if args.verbose:
            import traceback

            traceback.print_exc()
        else:
            print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


async def data_list_command(args) -> None:
    """Handle data list command."""
    try:
        # Initialize persistence service
        config = load_config(args.config)
        persistence_config = PersistenceConfig(
            storage_path=config.persistence_storage_path,
            cache_enabled=config.persistence_cache_enabled,
            cache_ttl_hours=config.persistence_cache_ttl_hours,
            max_cache_size=config.persistence_max_cache_size,
            auto_cleanup=config.persistence_auto_cleanup,
        )
        persistence_service = PersistenceServiceImpl(persistence_config)

        # Get evaluations
        evaluations = await persistence_service.list_evaluations(limit=args.limit)

        if args.format == "json":
            import json

            data = []
            for eval_record in evaluations:
                data.append(
                    {
                        "id": eval_record.id,
                        "prompt": eval_record.candidate.prompt,
                        "response": eval_record.candidate.response,
                        "overall_score": eval_record.result.aggregated.overall_score,
                        "evaluated_at": eval_record.evaluated_at.isoformat(),
                        "judge_model": eval_record.judge_model,
                    }
                )
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            # Table format
            print(f"{'ID':<36} {'Score':<6} {'Model':<15} {'Evaluated At':<20}")
            print("-" * 80)
            for eval_record in evaluations:
                print(
                    f"{eval_record.id:<36} "
                    f"{eval_record.result.aggregated.overall_score:<6.1f} "
                    f"{eval_record.judge_model:<15} "
                    f"{eval_record.evaluated_at.strftime('%Y-%m-%d %H:%M:%S'):<20}"
                )

    except Exception as e:
        raise CLIError(f"Error listing evaluations: {e}")


async def data_export_command(args) -> None:
    """Handle data export command."""
    try:
        # Initialize persistence service
        config = load_config(args.config)
        persistence_config = PersistenceConfig(
            storage_path=config.persistence_storage_path,
            cache_enabled=config.persistence_cache_enabled,
            cache_ttl_hours=config.persistence_cache_ttl_hours,
            max_cache_size=config.persistence_max_cache_size,
            auto_cleanup=config.persistence_auto_cleanup,
        )
        persistence_service = PersistenceServiceImpl(persistence_config)

        # Get evaluations
        evaluations = await persistence_service.list_evaluations(limit=args.limit)

        # Export to JSON
        import json

        data = []
        for eval_record in evaluations:
            data.append(
                {
                    "id": eval_record.id,
                    "candidate": {
                        "prompt": eval_record.candidate.prompt,
                        "response": eval_record.candidate.response,
                    },
                    "result": {
                        "overall_score": eval_record.result.aggregated.overall_score,
                        "criterion_scores": {
                            name: score.score
                            for name, score in eval_record.result.criterion_scores.items()
                        },
                    },
                    "metadata": {
                        "evaluated_at": eval_record.evaluated_at.isoformat(),
                        "judge_model": eval_record.judge_model,
                        "provider": eval_record.provider,
                        "criteria_hash": eval_record.criteria_hash,
                    },
                }
            )

        with open(args.output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Exported {len(data)} evaluations to {args.output_file}")

    except Exception as e:
        raise CLIError(f"Error exporting evaluations: {e}")


async def data_clean_cache_command(args) -> None:
    """Handle data clean-cache command."""
    try:
        # Initialize persistence service
        config = load_config(args.config)
        persistence_config = PersistenceConfig(
            storage_path=config.persistence_storage_path,
            cache_enabled=config.persistence_cache_enabled,
            cache_ttl_hours=config.persistence_cache_ttl_hours,
            max_cache_size=config.persistence_max_cache_size,
            auto_cleanup=config.persistence_auto_cleanup,
        )
        persistence_service = PersistenceServiceImpl(persistence_config)

        if not args.force:
            response = input("Are you sure you want to clean the cache? (y/N): ")
            if response.lower() != "y":
                print("Cache cleanup cancelled.")
                return

        # Clean cache
        await persistence_service.clean_cache()
        print("Cache cleaned successfully.")

    except Exception as e:
        raise CLIError(f"Error cleaning cache: {e}")


def cli_entry():
    """Entry point for setuptools console script."""
    asyncio.run(main())


if __name__ == "__main__":
    cli_entry()
