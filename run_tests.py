#!/usr/bin/env python3
"""
飞书群日常分析插件测试运行脚本

此脚本运行所有测试并提供结果摘要
"""

import sys
import subprocess
from pathlib import Path


def check_dependencies():
    """检查是否安装了所需的测试依赖"""
    try:
        import pytest
        import pytest_asyncio
        return True
    except ImportError:
        print("❌ 缺少测试依赖！")
        print("\n请安装所需的包：")
        print("  pip install pytest pytest-asyncio")
        return False


def run_tests(verbose=True, coverage=False):
    """运行测试套件"""
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
    print("运行飞书群日常分析插件测试套件")
    print("=" * 70)
    print()
    
    # Run tests
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    
    print()
    print("=" * 70)
    if result.returncode == 0:
        print("✅ 所有测试通过！")
    else:
        print("❌ 一些测试失败！")
    print("=" * 70)
    
    return result.returncode == 0


def run_specific_test(test_path):
    """运行特定的测试文件或测试"""
    if not check_dependencies():
        return False
    
    cmd = ["python", "-m", "pytest", test_path, "-v", "--color=yes"]
    
    print(f"正在运行：{test_path}")
    print("=" * 70)
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    
    return result.returncode == 0


def main():
    """主入口点"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="运行飞书群日常分析插件测试"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="运行测试并生成覆盖率报告"
    )
    parser.add_argument(
        "--test",
        type=str,
        help="运行特定的测试文件或测试（例如：tests/test_lark_integration.py）"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="以安静模式运行测试"
    )
    
    args = parser.parse_args()
    
    if args.test:
        success = run_specific_test(args.test)
    else:
        success = run_tests(verbose=not args.quiet, coverage=args.coverage)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
