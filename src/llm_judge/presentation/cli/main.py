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

from ...application.services.llm_judge_service import LLMJudge, CandidateResponse, EvaluationResult
from ...infrastructure.config.config import LLMConfig, load_config
from ...domain.evaluation.criteria import DefaultCriteria
from .batch_commands import add_batch_commands
from .multi_criteria_display import MultiCriteriaDisplayFormatter


class CLIError(Exception):
    """CLI-specific error for user-friendly error handling."""
    pass


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser."""
    parser = argparse.ArgumentParser(
        prog='llm-judge',
        description='LLM-as-a-Judge: Evaluate and compare language model responses',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Evaluate a single response
  llm-judge evaluate "What is AI?" "AI is artificial intelligence" --criteria "accuracy"
  
  # Compare two responses
  llm-judge compare "Explain ML" "Basic explanation" "Detailed explanation" --model-a gpt-4 --model-b claude-3
  
  # Use specific provider and model
  llm-judge evaluate "Question" "Answer" --provider openai --judge-model gpt-4
  
  # Use configuration file
  llm-judge evaluate "Question" "Answer" --config ./my-config.json
  
  # Output as JSON
  llm-judge evaluate "Question" "Answer" --output json
        """
    )
    
    # Global options
    parser.add_argument('--provider', choices=['openai', 'anthropic'], 
                       help='LLM provider to use as judge')
    parser.add_argument('--judge-model', help='Specific model to use as judge')
    parser.add_argument('--config', type=Path, help='Path to configuration file')
    parser.add_argument('--output', choices=['text', 'json'], default='text',
                       help='Output format (default: text)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Evaluate command
    eval_parser = subparsers.add_parser('evaluate', help='Evaluate a single response')
    eval_parser.add_argument('prompt', help='The prompt/question')
    eval_parser.add_argument('response', help='The response to evaluate')
    eval_parser.add_argument('--criteria', default='overall quality',
                            help='Evaluation criteria (default: "overall quality")')
    eval_parser.add_argument('--model', help='Model that generated the response')
    eval_parser.add_argument('--single-criterion', action='store_true',
                            help='Use single-criterion evaluation instead of multi-criteria')
    eval_parser.add_argument('--show-detailed', action='store_true',
                            help='Show detailed multi-criteria breakdown')
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare two responses')
    compare_parser.add_argument('prompt', help='The prompt/question')
    compare_parser.add_argument('response_a', help='First response to compare')
    compare_parser.add_argument('response_b', help='Second response to compare')
    compare_parser.add_argument('--model-a', help='Model that generated response A')
    compare_parser.add_argument('--model-b', help='Model that generated response B')
    
    # Add batch commands
    add_batch_commands(subparsers)
    
    return parser


def load_cli_config(config_path: Optional[Path], provider: Optional[str], judge_model: Optional[str]) -> LLMConfig:
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
    config = load_cli_config(args.config, args.provider, args.judge_model)
    
    candidate = CandidateResponse(
        prompt=args.prompt,
        response=args.response,
        model=args.model or "unknown"
    )
    
    judge = LLMJudge(config, judge_model=args.judge_model)
    
    try:
        if getattr(args, 'single_criterion', False):
            # Use legacy single-criterion evaluation
            result = await judge.evaluate_response(
                candidate, 
                args.criteria, 
                use_multi_criteria=False
            )
            return {
                'type': 'evaluation',
                'prompt': args.prompt,
                'response': args.response,
                'model': args.model or "unknown",
                'criteria': args.criteria,
                'score': result.score,
                'reasoning': result.reasoning,
                'confidence': result.confidence,
                'judge_model': judge.judge_model
            }
        else:
            # Use multi-criteria evaluation (default)
            multi_result = await judge.evaluate_multi_criteria(candidate)
            return {
                'type': 'multi_criteria_evaluation',
                'prompt': args.prompt,
                'response': args.response,
                'model': args.model or "unknown",
                'multi_criteria_result': multi_result,
                'judge_model': judge.judge_model,
                'show_detailed': getattr(args, 'show_detailed', False)
            }
    finally:
        await judge.close()


async def compare_command(args: argparse.Namespace) -> Dict[str, Any]:
    """Execute the compare command."""
    config = load_cli_config(args.config, args.provider, args.judge_model)
    
    candidate_a = CandidateResponse(
        prompt=args.prompt,
        response=args.response_a,
        model=args.model_a or "unknown"
    )
    
    candidate_b = CandidateResponse(
        prompt=args.prompt,
        response=args.response_b,
        model=args.model_b or "unknown"
    )
    
    judge = LLMJudge(config, judge_model=args.judge_model)
    
    try:
        result = await judge.compare_responses(candidate_a, candidate_b)
        return {
            'type': 'comparison',
            'prompt': args.prompt,
            'response_a': args.response_a,
            'response_b': args.response_b,
            'model_a': args.model_a or "unknown",
            'model_b': args.model_b or "unknown",
            'winner': result['winner'],
            'reasoning': result['reasoning'],
            'confidence': result.get('confidence', 0.0),
            'judge_model': judge.judge_model
        }
    finally:
        await judge.close()


def format_evaluation_output(result: Dict[str, Any], output_format: str) -> str:
    """Format evaluation result for display."""
    if output_format == 'json':
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
    output.append(result['reasoning'])
    
    return "\n".join(output)


def format_comparison_output(result: Dict[str, Any], output_format: str) -> str:
    """Format comparison result for display."""
    if output_format == 'json':
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
    
    winner = result['winner']
    if winner == 'tie':
        output.append("Result: TIE")
    else:
        output.append(f"Winner: Response {winner}")
    
    output.append(f"Confidence: {result['confidence']:.2f}")
    output.append("")
    output.append("Reasoning:")
    output.append(result['reasoning'])
    
    return "\n".join(output)


async def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'evaluate':
            result = await evaluate_command(args)
            
            if result['type'] == 'multi_criteria_evaluation':
                # Use multi-criteria display formatter
                formatter = MultiCriteriaDisplayFormatter()
                output = formatter.format_evaluation_result(
                    result['multi_criteria_result'], 
                    args.output
                )
            else:
                # Use legacy single-criterion formatter
                output = format_evaluation_output(result, args.output)
            
            print(output)
        elif args.command == 'compare':
            result = await compare_command(args)
            output = format_comparison_output(result, args.output)
            print(output)
        elif args.command in ['batch', 'create-sample-batch']:
            # Handle batch commands asynchronously
            exit_code = await args.func(args)
            sys.exit(exit_code)
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


def cli_entry():
    """Entry point for setuptools console script."""
    asyncio.run(main())


if __name__ == '__main__':
    cli_entry()