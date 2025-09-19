"""
LLM-as-a-Judge CLI entry point for direct module execution.

This allows running the CLI with: python -m src.llm_judge
"""

from .presentation.cli import cli_entry


def main():
    """Main entry point for direct module execution."""
    cli_entry()


if __name__ == "__main__":
    cli_entry()
