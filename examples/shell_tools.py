"""通用 shell 命令工具。"""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_command(*args: str) -> tuple[int, str]:
    """执行 shell 命令，返回 (returncode, output)。
    @param args: 命令及参数，如 ``run_command("git", "status")``
    """
    result = subprocess.run(
        list(args),
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        check=False,
    )
    parts = [text.strip() for text in (result.stdout, result.stderr) if text.strip()]
    return result.returncode, "\n".join(parts)
