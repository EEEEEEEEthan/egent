"""Shell 内置工具单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

import egent.builtin_tools.shell_tools
import egent.limits


def _python_command(code: str) -> str:
    if sys.platform == "win32":
        escaped_code = code.replace("'", "''")
        return f"& '{sys.executable}' -c '{escaped_code}'"
    return f'"{sys.executable}" -c "{code}"'


def _sleep_command(seconds: float) -> str:
    if sys.platform == "win32":
        return f"Start-Sleep -Seconds {seconds}"
    return _python_command(f"import time; time.sleep({seconds})")


def _long_output_command(character_count: int) -> str:
    if sys.platform == "win32":
        return f"Write-Output ('x' * {character_count})"
    return _python_command(f"print('x' * {character_count})")


def test_shell_runs_command() -> None:
    """shell 应执行命令并返回输出与退出码。"""
    result = egent.builtin_tools.shell_tools.shell(_python_command("print(42)"))

    assert "42" in result
    assert "exit_code: 0" in result


def test_shell_uses_working_directory(tmp_path: Path) -> None:
    """shell 应在指定目录中执行命令。"""
    subdirectory = tmp_path / "workspace"
    subdirectory.mkdir()

    result = egent.builtin_tools.shell_tools.shell(
        _python_command("import os; print(os.getcwd())"),
        working_directory=str(subdirectory),
    )

    assert str(subdirectory) in result
    assert "exit_code: 0" in result


def test_shell_rejects_missing_working_directory(tmp_path: Path) -> None:
    """shell 在工作目录不存在时应返回错误。"""
    result = egent.builtin_tools.shell_tools.shell("echo test", working_directory=str(tmp_path / "missing"))

    assert "目录不存在" in result


def test_shell_rejects_empty_command() -> None:
    """shell 在命令为空时应返回错误。"""
    result = egent.builtin_tools.shell_tools.shell("   ")

    assert "命令不能为空" in result


def test_shell_reports_nonzero_exit_code() -> None:
    """shell 应返回非零退出码。"""
    command = (
        _python_command("import sys; sys.exit(3)")
        if sys.platform != "win32"
        else "exit 3"
    )

    result = egent.builtin_tools.shell_tools.shell(command)

    assert "exit_code: 3" in result


def test_shell_times_out() -> None:
    """shell 在超时时应返回错误。"""
    result = egent.builtin_tools.shell_tools.shell(_sleep_command(2), block_until_ms=200)

    assert "超时" in result


def test_shell_returns_full_output() -> None:
    """shell 应返回完整输出（截断交由 conversation 统一处理）。"""
    character_count = egent.limits.TOOL_RESULT_MAX_CHARS + 100

    result = egent.builtin_tools.shell_tools.shell(_long_output_command(character_count))

    assert "输出被截断" not in result
    assert len(result) >= character_count
    assert "exit_code: 0" in result
