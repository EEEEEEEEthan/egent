"""Shell 命令内置工具。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import egent.builtin_tools.command_utils

__all__ = ["shell"]


def shell(
    command: str,
    working_directory: str | None = None,
    block_until_ms: int = 30_000,
) -> str:
    """执行 Shell 命令并返回标准输出、标准错误与退出码。

    @param command 要执行的 Shell 命令
    @param working_directory 工作目录绝对或相对路径，缺省为当前进程工作目录
    @param block_until_ms 最长等待毫秒数，缺省 30000
    """
    if not command.strip():
        raise ValueError("命令不能为空")
    resolved_directory = (
        Path.cwd() if working_directory is None else Path(working_directory).resolve()
    )
    if not resolved_directory.is_dir():
        raise FileNotFoundError(f"目录不存在：{working_directory}")
    run_kwargs = {
        "cwd": resolved_directory,
        "capture_output": True,
        "text": True,
        "timeout": max(block_until_ms, 1) / 1000,
        "encoding": "utf-8",
        "errors": "replace",
    }
    try:
        if sys.platform == "win32":
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                check=False,
                **run_kwargs,
            )
        else:
            completed = subprocess.run(command, shell=True, check=False, **run_kwargs)
    except subprocess.TimeoutExpired as timeout_error:
        raise TimeoutError(f"命令执行超时（{block_until_ms}ms）") from timeout_error
    return egent.builtin_tools.command_utils.format_command_result(
        completed.stdout, completed.stderr, completed.returncode
    )
