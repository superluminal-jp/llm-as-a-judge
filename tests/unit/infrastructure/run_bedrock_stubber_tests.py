#!/usr/bin/env python3
"""Test runner for Bedrock stubber-based tests.

This script demonstrates how to run the comprehensive stubber-based tests
for the AWS Bedrock client. It provides detailed output and can be used
for both development and CI/CD pipelines.
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_tests(test_file: str, verbose: bool = False, coverage: bool = False) -> int:
    """Run the specified test file with optional coverage."""
    cmd = ["python", "-m", "pytest", test_file]

    if verbose:
        cmd.append("-v")

    if coverage:
        cmd.extend(
            [
                "--cov=src.llm_judge.infrastructure.clients.bedrock_client",
                "--cov-report=term-missing",
            ]
        )

    # Add test discovery
    cmd.extend(["-x", "--tb=short"])

    print(f"Running command: {' '.join(cmd)}")
    print("=" * 60)

    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent.parent.parent)
    return result.returncode


def run_all_bedrock_tests(verbose: bool = False, coverage: bool = False) -> int:
    """Run all Bedrock-related tests."""
    test_files = [
        "tests/unit/infrastructure/test_bedrock_client_stubber.py",
        "tests/unit/infrastructure/test_bedrock_client.py",
        "tests/unit/infrastructure/test_bedrock_client_comprehensive.py",
    ]

    total_failures = 0

    for test_file in test_files:
        print(f"\n{'='*80}")
        print(f"Running {test_file}")
        print(f"{'='*80}")

        result = run_tests(test_file, verbose, coverage)
        if result != 0:
            total_failures += 1
            print(f"❌ {test_file} failed")
        else:
            print(f"✅ {test_file} passed")

    return total_failures


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(
        description="Run Bedrock stubber-based tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all Bedrock tests
  python run_bedrock_stubber_tests.py --all
  
  # Run only stubber tests with verbose output
  python run_bedrock_stubber_tests.py --stubber --verbose
  
  # Run with coverage
  python run_bedrock_stubber_tests.py --all --coverage
  
  # Run specific test file
  python run_bedrock_stubber_tests.py --file tests/unit/infrastructure/test_bedrock_client_stubber.py
        """,
    )

    parser.add_argument("--all", action="store_true", help="Run all Bedrock test files")

    parser.add_argument(
        "--stubber", action="store_true", help="Run only stubber-based tests"
    )

    parser.add_argument("--file", type=str, help="Run specific test file")

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    parser.add_argument(
        "--coverage", action="store_true", help="Run with coverage reporting"
    )

    args = parser.parse_args()

    if not any([args.all, args.stubber, args.file]):
        parser.print_help()
        return 1

    print("🚀 Bedrock Stubber Test Runner")
    print("=" * 60)

    if args.all:
        failures = run_all_bedrock_tests(args.verbose, args.coverage)
    elif args.stubber:
        failures = run_tests(
            "tests/unit/infrastructure/test_bedrock_client_stubber.py",
            args.verbose,
            args.coverage,
        )
    elif args.file:
        failures = run_tests(args.file, args.verbose, args.coverage)

    print("\n" + "=" * 60)
    if failures == 0:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"💥 {failures} test file(s) failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
