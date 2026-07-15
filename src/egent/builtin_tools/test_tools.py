"""pytest 回归测试工具。"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

import egent.builtin_tools.command_utils

__all__ = ["execute_pytest", "run_regression_test"]


def execute_pytest(targets: list[str] | None = None) -> tuple[bool, str]:
    """跑 pytest，返回 (passed, output)。"""
    command = [sys.executable, "-m", "pytest", *([] if targets is None else targets)]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
            check=False,
        )
    except OSError as error:
        return False, str(error)
    output = egent.builtin_tools.command_utils.format_command_result(
        result.stdout,
        result.stderr,
        result.returncode,
    )
    return result.returncode == 0, output


def run_regression_test(targets: str = "") -> str:
    """运行 pytest 回归测试，验证当前代码状态。
    @param targets: 与本次开发相关的测试路径或节点（如 tests/test_foo.py::test_bar），空格分隔；留空则跑全量
    """
    parsed_targets = (
        [part for part in shlex.split(targets, posix=False) if part]
        if targets.strip()
        else None
    )
    passed, output = execute_pytest(parsed_targets)
    if passed:
        scope = f"（{targets}）" if targets.strip() else "（全量）"
        return f"回归测试通过{scope}"
    scope_label = f"目标 {targets}" if targets.strip() else "全量回归测试"
    return f"{scope_label}未通过：\n{output}"
