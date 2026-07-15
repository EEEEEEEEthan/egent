"""Git 命令工具。"""

from __future__ import annotations

import subprocess
from pathlib import Path


def git_commit(commit_message: str) -> str:
    """将所有变更加入暂存区并提交。
    @param commit_message: 提交信息
    """
    add_result = subprocess.run(
        ["git", "add", "-A"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        check=False,
    )
    commit_result = subprocess.run(
        ["git", "commit", "-m", commit_message],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        check=False,
    )
    parts = [
        text.strip()
        for text in (
            add_result.stdout,
            add_result.stderr,
            commit_result.stdout,
            commit_result.stderr,
        )
        if text.strip()
    ]
    output = "\n".join(parts)
    if add_result.returncode != 0 or commit_result.returncode != 0:
        return f"git 提交失败：\n{output}"
    return output or "git 提交成功"


def git_diff(staged: bool = False, cached: bool = False) -> str:
    """查看代码变更 diff。
    @param staged: True 查看已暂存到 index 的变更（git diff --staged）
    @param cached: True 查看工作区相对 HEAD 的全部变更（git diff HEAD）。与 staged 互斥，cached 优先。
    """
    args = ["git", "diff"]
    if cached:
        args.append("HEAD")
    elif staged:
        args.append("--staged")
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        check=False,
    )
    output = result.stdout.strip()
    if not output:
        return "没有 diff（工作区干净，或没有可展示的变更）"
    return output


def reset_git_workspace() -> tuple[bool, str]:
    """将工作区强制恢复为 HEAD 干净状态，返回 (success, output)。"""
    cwd = Path.cwd()
    try:
        reset = subprocess.run(
            ["git", "reset", "--hard", "HEAD"],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
        clean = subprocess.run(
            ["git", "clean", "-fd"],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
    except OSError as error:
        return False, str(error)
    outputs = [
        part.strip()
        for part in (reset.stdout, reset.stderr, clean.stdout, clean.stderr)
        if part.strip()
    ]
    output = "\n".join(outputs) if outputs else "工作区已恢复为 HEAD 干净状态"
    if reset.returncode != 0 or clean.returncode != 0:
        return False, output
    return True, output
