"""
Batch processing CLI commands with progress indicators.

Provides command-line interface for batch evaluation processing with
real-time progress feedback and comprehensive result reporting.
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

# Rich library for enhanced CLI output (will fallback gracefully if not available)
try:
    from rich.console import Console
    from rich.progress import (
        Progress,
        TaskID,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        MofNCompleteColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ...application.services.batch_service import BatchProcessingService
from ...application.services.llm_judge_service import LLMJudge
from ...domain.batch import BatchProgress
from ...infrastructure.config.config import LLMConfig, load_config
from .config_helper import CLIConfigManager


logger = logging.getLogger(__name__)


class BatchProgressTracker:
    """Progress tracker with rich formatting or fallback to basic output."""

    def __init__(self, use_rich: bool = True):
        self.use_rich = use_rich and RICH_AVAILABLE
        self.console = Console() if self.use_rich else None
        self.progress = None
        self.task_id = None
        self.start_time = None

    def start(self, total_items: int, batch_name: str = "Batch Processing"):
        """Start progress tracking."""
        self.start_time = time.time()

        if self.use_rich:
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.fields[batch_name]}", justify="left"),
                BarColumn(bar_width=40),
                MofNCompleteColumn(),
                TextColumn("•"),
                TimeElapsedColumn(),
                TextColumn("•"),
                TimeRemainingColumn(),
                console=self.console,
            )
            self.progress.start()
            self.task_id = self.progress.add_task(
                "processing", total=total_items, batch_name=batch_name
            )
        else:
            print(f"Starting {batch_name} with {total_items} items...")

    def update(self, progress_data: BatchProgress):
        """Update progress display."""
        completed = progress_data.completed_items + progress_data.failed_items

        if self.use_rich and self.progress and self.task_id:
            # Update rich progress bar
            self.progress.update(
                self.task_id,
                completed=completed,
                description=f"Processing ({progress_data.completed_items} success, {progress_data.failed_items} failed)",
            )
        else:
            # Fallback to basic progress
            percentage = (
                (completed / progress_data.total_items) * 100
                if progress_data.total_items > 0
                else 0
            )
            elapsed = time.time() - self.start_time if self.start_time else 0

            print(
                f"\rProgress: {completed}/{progress_data.total_items} ({percentage:.1f}%) "
                f"- {progress_data.completed_items} success, {progress_data.failed_items} failed "
                f"- {elapsed:.1f}s elapsed",
                end="",
                flush=True,
            )

    def finish(self):
        """Finish progress tracking."""
        if self.use_rich and self.progress:
            self.progress.stop()
        else:
            print()  # New line after progress updates


class BatchCLICommands:
    """CLI commands for batch processing."""

    def __init__(self):
        self.config_manager = CLIConfigManager()

    def add_batch_subparser(self, subparsers):
        """Add batch command subparser."""
        batch_parser = subparsers.add_parser(
            "batch",
            help="Process batch evaluations from file",
            description="Process multiple evaluations from JSONL, CSV, or JSON files",
        )

        # Input/output arguments
        batch_parser.add_argument(
            "input_file", type=str, help="Input file path (JSONL, CSV, or JSON format)"
        )

        batch_parser.add_argument(
            "--output",
            "-o",
            type=str,
            help="Output file path for results (JSON format)",
        )

        # Batch configuration
        batch_parser.add_argument(
            "--max-concurrent",
            type=int,
            default=10,
            help="Maximum concurrent evaluations (default: 10)",
        )

        batch_parser.add_argument(
            "--max-retries",
            type=int,
            default=3,
            help="Maximum retries per failed item (default: 3)",
        )

        batch_parser.add_argument(
            "--no-retry", action="store_true", help="Disable retries for failed items"
        )

        batch_parser.add_argument(
            "--fail-fast", action="store_true", help="Stop processing on first error"
        )

        batch_parser.add_argument(
            "--batch-name", type=str, help="Optional name for the batch"
        )

        # Progress and output options
        batch_parser.add_argument(
            "--no-progress", action="store_true", help="Disable progress indicators"
        )

        batch_parser.add_argument(
            "--quiet", action="store_true", help="Minimal output (only final summary)"
        )

        batch_parser.set_defaults(func=self.handle_batch_command)

        # Add create-sample subcommand
        sample_parser = subparsers.add_parser(
            "create-sample-batch",
            help="Create sample batch file",
            description="Create a sample batch file for testing",
        )

        sample_parser.add_argument(
            "output_file", type=str, help="Output file path for sample batch"
        )

        sample_parser.add_argument(
            "--format",
            choices=["jsonl", "csv", "json"],
            default="jsonl",
            help="Output format (default: jsonl)",
        )

        sample_parser.set_defaults(func=self.handle_create_sample_command)

        return batch_parser

    async def handle_batch_command(self, args) -> int:
        """Handle batch processing command."""
        try:
            # Load configuration
            config = await self._load_config(args)

            # Create LLM judge
            judge = LLMJudge(config=config)

            # Create batch service
            batch_service = BatchProcessingService(
                llm_judge=judge, max_workers=args.max_concurrent
            )

            # Prepare batch configuration
            batch_config = {
                "max_concurrent_items": args.max_concurrent,
                "retry_failed_items": not args.no_retry,
                "max_retries_per_item": args.max_retries,
                "continue_on_error": not args.fail_fast,
                "name": args.batch_name,
                "judge_provider": config.default_provider,
                "judge_model": getattr(config, f"{config.default_provider}_model"),
            }

            # Set up progress tracking
            progress_tracker = None
            if not args.no_progress and not args.quiet:
                progress_tracker = BatchProgressTracker(use_rich=True)

            # Progress callback
            def progress_callback(progress: BatchProgress):
                if progress_tracker:
                    progress_tracker.update(progress)

            if not args.quiet:
                print(f"Processing batch from: {args.input_file}")
                if args.output:
                    print(f"Results will be saved to: {args.output}")

            # Process batch
            result = await batch_service.process_batch_from_file(
                file_path=args.input_file,
                output_path=args.output,
                batch_config=batch_config,
                progress_callback=progress_callback if not args.no_progress else None,
            )

            # Finish progress tracking
            if progress_tracker:
                progress_tracker.finish()

            # Display results
            await self._display_batch_results(result, args)

            # Cleanup
            await judge.close()

            return 0 if result.success_rate > 0.5 else 1

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            if not args.quiet:
                print(f"Error: {e}", file=sys.stderr)
            return 1

    async def handle_create_sample_command(self, args) -> int:
        """Handle create sample batch command."""
        try:
            # Create dummy judge for the service
            config = LLMConfig()  # Mock config
            judge = LLMJudge(config=config)
            batch_service = BatchProcessingService(judge)

            # Create sample file
            await batch_service.create_sample_batch_file(
                file_path=args.output_file, format=args.format
            )

            print(f"Sample batch file created: {args.output_file}")
            print(f"Format: {args.format.upper()}")
            print(
                f"You can now edit this file and process it with: llm-judge batch {args.output_file}"
            )

            await judge.close()
            return 0

        except Exception as e:
            print(f"Error creating sample file: {e}", file=sys.stderr)
            return 1

    async def _load_config(self, args) -> LLMConfig:
        """Load configuration from args and files."""
        try:
            # Load base config
            config = load_config()

            # Override with CLI args if provided
            if hasattr(args, "provider") and args.provider:
                config.default_provider = args.provider

            if hasattr(args, "judge_model") and args.judge_model:
                if config.default_provider == "openai":
                    config.openai_model = args.judge_model
                elif config.default_provider == "anthropic":
                    config.anthropic_model = args.judge_model

            return config

        except Exception as e:
            logger.error(f"Configuration loading failed: {e}")
            # Return mock config for basic functionality
            return LLMConfig()

    async def _display_batch_results(self, result, args):
        """Display batch processing results."""
        if args.quiet:
            # Minimal output
            print(
                f"{result.completed_items_count}/{result.total_items} successful ({result.success_rate:.1%})"
            )
            return

        if RICH_AVAILABLE and not args.output == "json":
            self._display_rich_results(result)
        else:
            self._display_basic_results(result)

    def _display_rich_results(self, result):
        """Display results using Rich formatting."""
        console = Console()

        # Main summary panel
        summary_text = f"""
Batch ID: {result.batch_request.batch_id}
Status: {result.status.value.title()}
Total Items: {result.total_items}
Successful: {result.completed_items_count}
Failed: {result.failed_items_count}
Success Rate: {result.success_rate:.1%}
Processing Time: {result.processing_duration:.1f}s
"""

        if result.average_processing_time:
            summary_text += f"Avg Time/Item: {result.average_processing_time:.2f}s\n"

        console.print(
            Panel(summary_text.strip(), title="[bold]Batch Results Summary[/bold]")
        )

        # Detailed results table if there are failures
        if result.failed_items_count > 0:
            console.print("\n[bold red]Failed Items:[/bold red]")

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Item ID", style="cyan")
            table.add_column("Type", style="green")
            table.add_column("Error", style="red")

            for item in result.failed_items[:10]:  # Show first 10 failures
                table.add_row(
                    item.item_id[:8] + "...",
                    item.evaluation_type.value,
                    (
                        item.error[:50] + "..."
                        if item.error and len(item.error) > 50
                        else item.error or "Unknown"
                    ),
                )

            console.print(table)

            if len(result.failed_items) > 10:
                console.print(f"... and {len(result.failed_items) - 10} more failures")

        # Success message
        if result.success_rate > 0.8:
            console.print(
                "\n[bold green]✓ Batch processing completed successfully![/bold green]"
            )
        elif result.success_rate > 0.5:
            console.print(
                "\n[bold yellow]⚠ Batch processing completed with some failures[/bold yellow]"
            )
        else:
            console.print(
                "\n[bold red]✗ Batch processing had significant failures[/bold red]"
            )

    def _display_basic_results(self, result):
        """Display results using basic text formatting."""
        print("\n" + "=" * 50)
        print("BATCH RESULTS SUMMARY")
        print("=" * 50)
        print(f"Batch ID: {result.batch_request.batch_id}")
        print(f"Status: {result.status.value.title()}")
        print(f"Total Items: {result.total_items}")
        print(f"Successful: {result.completed_items_count}")
        print(f"Failed: {result.failed_items_count}")
        print(f"Success Rate: {result.success_rate:.1%}")
        print(f"Processing Time: {result.processing_duration:.1f}s")

        if result.average_processing_time:
            print(f"Avg Time/Item: {result.average_processing_time:.2f}s")

        if result.failed_items_count > 0:
            print(f"\nFirst {min(5, len(result.failed_items))} failures:")
            for i, item in enumerate(result.failed_items[:5]):
                print(f"  {i+1}. {item.item_id[:8]}... - {item.error}")

        print("=" * 50)


# Function to integrate with main CLI
def add_batch_commands(subparsers):
    """Add batch commands to CLI subparsers."""
    batch_cli = BatchCLICommands()
    return batch_cli.add_batch_subparser(subparsers)
