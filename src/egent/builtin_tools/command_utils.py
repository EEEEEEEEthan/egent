"""命令输出格式化辅助函数。"""

from __future__ import annotations


def format_command_result(stdout: str, stderr: str, returncode: int) -> str:
    """将 stdout/stderr/exit_code 拼接为统一格式的字符串（不做截断）。"""
    sections: list[str] = []
    if stdout:
        sections.append(stdout.rstrip("\n"))
    if stderr:
        if sections:
            sections.append("")
        sections.append(stderr.rstrip("\n"))
    sections.append(f"exit_code: {returncode}")
    return "\n".join(sections)
