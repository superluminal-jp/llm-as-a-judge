"""
Multi-criteria evaluation result display utilities for CLI.

Provides rich formatting for comprehensive multi-dimensional evaluation results.
"""

from typing import Dict, Any, List
import json

# Rich library for enhanced output (with fallback)
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress
    from rich.text import Text
    from rich.columns import Columns
    from rich.padding import Padding
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ...domain.evaluation.results import MultiCriteriaResult
from ...domain.evaluation.criteria import CriterionType


class MultiCriteriaDisplayFormatter:
    """Formatter for multi-criteria evaluation results."""
    
    def __init__(self, use_rich: bool = True):
        self.use_rich = use_rich and RICH_AVAILABLE
        self.console = Console() if self.use_rich else None
    
    def format_evaluation_result(self, result: MultiCriteriaResult, output_format: str = "text") -> str:
        """Format multi-criteria evaluation result."""
        if output_format == "json":
            return self._format_json_output(result)
        elif self.use_rich:
            return self._format_rich_output(result)
        else:
            return self._format_basic_output(result)
    
    def _format_json_output(self, result: MultiCriteriaResult) -> str:
        """Format as JSON output."""
        output_data = {
            "type": "multi_criteria_evaluation",
            "overall_score": result.aggregated.overall_score if result.aggregated else None,
            "overall_confidence": result.aggregated.confidence if result.aggregated else None,
            "criteria_count": len(result.criterion_scores),
            "judge_model": result.judge_model,
            "evaluation_timestamp": result.evaluation_timestamp.isoformat(),
        }
        
        # Add aggregated statistics
        if result.aggregated:
            output_data.update({
                "weighted_score": result.aggregated.weighted_score,
                "mean_score": result.aggregated.mean_score,
                "median_score": result.aggregated.median_score,
                "score_std": result.aggregated.score_std,
                "score_range": [result.aggregated.min_score, result.aggregated.max_score]
            })
        
        # Individual criterion scores
        output_data["criterion_scores"] = []
        for cs in result.criterion_scores:
            criterion_data = {
                "criterion": cs.criterion_name,
                "score": cs.score,
                "percentage": cs.percentage_score,
                "reasoning": cs.reasoning,
                "confidence": cs.confidence,
                "weight": cs.weight
            }
            output_data["criterion_scores"].append(criterion_data)
        
        # Qualitative feedback
        if result.overall_reasoning:
            output_data["overall_reasoning"] = result.overall_reasoning
        if result.strengths:
            output_data["strengths"] = result.strengths
        if result.weaknesses:
            output_data["weaknesses"] = result.weaknesses
        if result.suggestions:
            output_data["suggestions"] = result.suggestions
        
        return json.dumps(output_data, indent=2, ensure_ascii=False)
    
    def _format_rich_output(self, result: MultiCriteriaResult) -> str:
        """Format with Rich library for enhanced display."""
        console = Console(record=True)
        
        # Main header
        console.print("\n[bold blue]🎯 Multi-Criteria LLM Evaluation Results[/bold blue]", justify="center")
        console.print("=" * 80, style="dim")
        
        # Overall score panel
        if result.aggregated:
            score_color = self._get_score_color(result.aggregated.overall_score)
            overall_panel = Panel(
                f"[bold {score_color}]{result.aggregated.overall_score:.1f}/5.0[/bold {score_color}]\n"
                f"Confidence: {result.aggregated.confidence:.1%}\n"
                f"Based on {len(result.criterion_scores)} criteria",
                title="[bold]Overall Score[/bold]",
                border_style=score_color
            )
            console.print(overall_panel)
        
        # Detailed criterion scores table
        if result.criterion_scores:
            console.print("\n[bold]📊 Detailed Criterion Scores[/bold]")
            table = Table(show_header=True, header_style="bold magenta", border_style="blue")
            table.add_column("Criterion", style="cyan", width=15)
            table.add_column("Score", justify="center", width=8)
            table.add_column("Weight", justify="center", width=8)
            table.add_column("Confidence", justify="center", width=10)
            table.add_column("Reasoning", width=50)
            
            for cs in sorted(result.criterion_scores, key=lambda x: x.score, reverse=True):
                score_color = self._get_score_color(cs.score)
                score_bar = self._create_score_bar(cs.score, cs.max_score)
                
                table.add_row(
                    f"[bold]{cs.criterion_name}[/bold]",
                    f"[{score_color}]{cs.score:.1f}/5[/{score_color}]",
                    f"{cs.weight:.1%}",
                    f"{cs.confidence:.1%}",
                    self._truncate_text(cs.reasoning, 45)
                )
            
            console.print(table)
        
        # Statistics summary
        if result.aggregated and len(result.criterion_scores) > 1:
            console.print(f"\n[bold]📈 Score Statistics[/bold]")
            stats_table = Table(show_header=False, border_style="dim")
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Value", justify="right")
            
            stats_table.add_row("Mean Score", f"{result.aggregated.mean_score:.2f}")
            stats_table.add_row("Median Score", f"{result.aggregated.median_score:.2f}")
            stats_table.add_row("Score Range", f"{result.aggregated.min_score:.1f} - {result.aggregated.max_score:.1f}")
            stats_table.add_row("Standard Deviation", f"{result.aggregated.score_std:.2f}")
            
            console.print(Padding(stats_table, (0, 4)))
        
        # Qualitative feedback sections
        if result.overall_reasoning:
            console.print(f"\n[bold]💭 Overall Assessment[/bold]")
            console.print(Panel(result.overall_reasoning, border_style="green"))
        
        if result.strengths:
            console.print(f"\n[bold green]✅ Strengths[/bold green]")
            for strength in result.strengths:
                console.print(f"  • {strength}")
        
        if result.weaknesses:
            console.print(f"\n[bold red]⚠️ Areas for Improvement[/bold red]")
            for weakness in result.weaknesses:
                console.print(f"  • {weakness}")
        
        if result.suggestions:
            console.print(f"\n[bold blue]💡 Suggestions[/bold blue]")
            for suggestion in result.suggestions:
                console.print(f"  • {suggestion}")
        
        # Metadata
        console.print(f"\n[dim]Judge Model: {result.judge_model}")
        if result.processing_duration:
            console.print(f"[dim]Processing Time: {result.processing_duration:.2f}s")
        console.print(f"[dim]Evaluation Time: {result.evaluation_timestamp.strftime('%Y-%m-%d %H:%M:%S')}[/dim]")
        
        return console.export_text()
    
    def _format_basic_output(self, result: MultiCriteriaResult) -> str:
        """Format with basic text for systems without Rich."""
        lines = []
        
        # Header
        lines.append("=" * 60)
        lines.append("🎯 Multi-Criteria LLM Evaluation Results")
        lines.append("=" * 60)
        
        # Overall score
        if result.aggregated:
            lines.append(f"\nOverall Score: {result.aggregated.overall_score:.1f}/5.0")
            lines.append(f"Confidence: {result.aggregated.confidence:.1%}")
            lines.append(f"Based on {len(result.criterion_scores)} criteria")
        
        # Individual scores
        if result.criterion_scores:
            lines.append(f"\nDetailed Criterion Scores:")
            lines.append("-" * 40)
            
            for cs in sorted(result.criterion_scores, key=lambda x: x.score, reverse=True):
                lines.append(f"\n{cs.criterion_name.upper()}: {cs.score:.1f}/5 (Weight: {cs.weight:.1%})")
                lines.append(f"  Confidence: {cs.confidence:.1%}")
                lines.append(f"  Reasoning: {cs.reasoning}")
        
        # Statistics
        if result.aggregated and len(result.criterion_scores) > 1:
            lines.append(f"\nScore Statistics:")
            lines.append(f"  Mean: {result.aggregated.mean_score:.2f}")
            lines.append(f"  Median: {result.aggregated.median_score:.2f}")
            lines.append(f"  Range: {result.aggregated.min_score:.1f} - {result.aggregated.max_score:.1f}")
            lines.append(f"  Std Dev: {result.aggregated.score_std:.2f}")
        
        # Qualitative feedback
        if result.overall_reasoning:
            lines.append(f"\nOverall Assessment:")
            lines.append(result.overall_reasoning)
        
        if result.strengths:
            lines.append(f"\nStrengths:")
            for strength in result.strengths:
                lines.append(f"  • {strength}")
        
        if result.weaknesses:
            lines.append(f"\nAreas for Improvement:")
            for weakness in result.weaknesses:
                lines.append(f"  • {weakness}")
        
        if result.suggestions:
            lines.append(f"\nSuggestions:")
            for suggestion in result.suggestions:
                lines.append(f"  • {suggestion}")
        
        # Metadata
        lines.append(f"\n" + "-" * 40)
        lines.append(f"Judge Model: {result.judge_model}")
        if result.processing_duration:
            lines.append(f"Processing Time: {result.processing_duration:.2f}s")
        lines.append(f"Evaluation Time: {result.evaluation_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(lines)
    
    def _get_score_color(self, score: float) -> str:
        """Get color based on score value."""
        if score >= 4.5:
            return "bright_green"
        elif score >= 4.0:
            return "green"
        elif score >= 3.5:
            return "yellow"
        elif score >= 3.0:
            return "orange3" 
        elif score >= 2.0:
            return "red"
        else:
            return "bright_red"
    
    def _create_score_bar(self, score: float, max_score: int) -> str:
        """Create a simple score bar."""
        percentage = score / max_score
        filled_chars = int(percentage * 10)
        bar = "█" * filled_chars + "░" * (10 - filled_chars)
        return f"[{self._get_score_color(score)}]{bar}[/{self._get_score_color(score)}]"
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to max length with ellipsis."""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."
    
    def format_comparison_result(self, result: Dict[str, Any], output_format: str = "text") -> str:
        """Format comparison result (legacy support)."""
        if output_format == "json":
            return json.dumps(result, indent=2)
        
        lines = []
        lines.append("=== LLM-as-a-Judge Comparison ===")
        lines.append(f"Judge Model: {result.get('judge_model', 'unknown')}")
        lines.append("")
        lines.append(f"Prompt: {result.get('prompt', '')}")
        lines.append("")
        lines.append(f"Response A ({result.get('model_a', 'unknown')}): {result.get('response_a', '')}")
        lines.append(f"Response B ({result.get('model_b', 'unknown')}): {result.get('response_b', '')}")
        lines.append("")
        
        winner = result.get('winner', 'tie')
        if winner == 'tie':
            lines.append("Result: TIE")
        else:
            lines.append(f"Winner: Response {winner}")
        
        lines.append(f"Confidence: {result.get('confidence', 0):.2f}")
        lines.append("")
        lines.append("Reasoning:")
        lines.append(result.get('reasoning', ''))
        
        return "\n".join(lines)