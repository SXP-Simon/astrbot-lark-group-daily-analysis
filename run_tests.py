#!/usr/bin/env python3
"""
Test runner script for astrbot-lark-group-daily-analysis plugin.

This script runs all tests and provides a summary of results.
"""

import sys
import subprocess
from pathlib import Path


def check_dependencies():
    """Check if required test dependencies are installed"""
    try:
        import pytest
        import pytest_asyncio
        return True
    except ImportError:
        print("❌ Missing test dependencies!")
        print("\nPlease install required packages:")
        print("  pip install pytest pytest-asyncio")
        return False


def run_tests(verbose=True, coverage=False):
    """Run the test suite"""
    if not check_dependencies():
        return False
    
    # Build pytest command
    cmd = ["python", "-m", "pytest", "tests/"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=src", "--cov-report=term", "--cov-report=html"])
    
    # Add color output
    cmd.append("--color=yes")
    
    print("=" * 70)
    print("Running Test Suite for astrbot-lark-group-daily-analysis")
    print("=" * 70)
    print()
    
    # Run tests
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    
    print()
    print("=" * 70)
    if result.returncode == 0:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
    print("=" * 70)
    
    return result.returncode == 0


def run_specific_test(test_path):
    """Run a specific test file or test"""
    if not check_dependencies():
        return False
    
    cmd = ["python", "-m", "pytest", test_path, "-v", "--color=yes"]
    
    print(f"Running: {test_path}")
    print("=" * 70)
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    
    return result.returncode == 0


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run tests for astrbot-lark-group-daily-analysis plugin"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run tests with coverage report"
    )
    parser.add_argument(
        "--test",
        type=str,
        help="Run specific test file or test (e.g., tests/test_lark_integration.py)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Run tests in quiet mode"
    )
    
    args = parser.parse_args()
    
    if args.test:
        success = run_specific_test(args.test)
    else:
        success = run_tests(verbose=not args.quiet, coverage=args.coverage)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
