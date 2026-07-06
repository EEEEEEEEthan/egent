"""Git 内置工具单元测试。"""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import egent.builtin_tools.git_tools as git_tools_mod
import egent.tool


def test_read_only_tools_contains_expected_functions() -> None:
    """read_only_tools 应包含 6 个只读工具函数。"""
    expected = {
        git_tools_mod.git_status,
        git_tools_mod.git_branch,
        git_tools_mod.git_log,
        git_tools_mod.git_diff,
        git_tools_mod.git_remote,
        git_tools_mod.git_tag,
    }

    assert set(git_tools_mod.read_only_tools) == expected
    assert len(git_tools_mod.read_only_tools) == 6


def test_write_only_tools_contains_expected_functions() -> None:
    """write_only_tools 应包含 12 个写入工具函数。"""
    expected = {
        git_tools_mod.git_init,
        git_tools_mod.git_clone,
        git_tools_mod.git_add,
        git_tools_mod.git_commit,
        git_tools_mod.git_push,
        git_tools_mod.git_pull,
        git_tools_mod.git_fetch,
        git_tools_mod.git_checkout,
        git_tools_mod.git_merge,
        git_tools_mod.git_reset,
        git_tools_mod.git_stash,
        git_tools_mod.git_clean,
    }

    assert set(git_tools_mod.write_only_tools) == expected
    assert len(git_tools_mod.write_only_tools) == 12


def test_no_overlap_between_read_and_write() -> None:
    """read_only_tools 与 write_only_tools 不应有交集。"""
    overlap = set(git_tools_mod.read_only_tools) & set(git_tools_mod.write_only_tools)

    assert overlap == set(), f"重叠函数：{overlap}"


def test_all_18_tools_covered() -> None:
    """两个列表合计应覆盖全部 18 个 git 工具函数。"""
    all_18 = {
        git_tools_mod.git_status, git_tools_mod.git_branch,
        git_tools_mod.git_log, git_tools_mod.git_diff,
        git_tools_mod.git_remote, git_tools_mod.git_tag,
        git_tools_mod.git_init, git_tools_mod.git_clone,
        git_tools_mod.git_add, git_tools_mod.git_commit,
        git_tools_mod.git_push, git_tools_mod.git_pull,
        git_tools_mod.git_fetch, git_tools_mod.git_checkout,
        git_tools_mod.git_merge, git_tools_mod.git_reset,
        git_tools_mod.git_stash, git_tools_mod.git_clean,
    }
    combined = set(git_tools_mod.read_only_tools) | set(git_tools_mod.write_only_tools)

    assert combined == all_18
    assert len(combined) == 18


def test_lists_contain_functions_not_strings() -> None:
    """列表元素应为函数对象而非字符串。"""
    for tool in git_tools_mod.read_only_tools + git_tools_mod.write_only_tools:
        assert inspect.isfunction(tool), f"{tool!r} 不是函数对象"


def test_resolve_tools_accepts_read_only_tools() -> None:
    """resolve_tools 应能接受 read_only_tools 列表。"""
    api_tools, handlers = egent.tool.resolve_tools(git_tools_mod.read_only_tools)

    assert len(api_tools) == 6
    assert len(handlers) == 6
    assert "git_status" in handlers
    assert "git_branch" in handlers
    assert "git_log" in handlers
    assert "git_diff" in handlers
    assert "git_remote" in handlers
    assert "git_tag" in handlers


def test_resolve_tools_accepts_write_only_tools() -> None:
    """resolve_tools 应能接受 write_only_tools 列表。"""
    api_tools, handlers = egent.tool.resolve_tools(git_tools_mod.write_only_tools)

    assert len(api_tools) == 12
    assert len(handlers) == 12
    for name in ("git_init", "git_clone", "git_add", "git_commit",
                 "git_push", "git_pull", "git_fetch", "git_checkout",
                 "git_merge", "git_reset", "git_stash", "git_clean"):
        assert name in handlers


def test_read_only_tools_are_exported_in_all() -> None:
    """read_only_tools 和 write_only_tools 应在 __all__ 中导出。"""
    assert "read_only_tools" in git_tools_mod.__all__
    assert "write_only_tools" in git_tools_mod.__all__


def test_git_diff_shows_unstaged_changes(tmp_path: Path) -> None:
    """git_diff 应显示未暂存的更改。"""
    _init_test_repo(tmp_path)
    (tmp_path / "readme.txt").write_text("hello", encoding="utf-8")
    _run_git(["add", "."], tmp_path)
    _run_git(["commit", "-m", "initial"], tmp_path)
    (tmp_path / "readme.txt").write_text("hello world", encoding="utf-8")

    result = git_tools_mod.git_diff(str(tmp_path))

    assert "hello world" in result
    assert "exit_code: 0" in result


def test_git_diff_cached_shows_staged_changes(tmp_path: Path) -> None:
    """git diff --cached 应显示已暂存但未提交的更改。"""
    _init_test_repo(tmp_path)
    (tmp_path / "readme.txt").write_text("hello", encoding="utf-8")
    _run_git(["add", "."], tmp_path)
    _run_git(["commit", "-m", "initial"], tmp_path)
    (tmp_path / "readme.txt").write_text("staged change", encoding="utf-8")
    _run_git(["add", "."], tmp_path)

    staged_result = _run_git(["diff", "--cached"], tmp_path)

    assert "staged change" in staged_result
    assert "exit_code: 0" in staged_result


def test_collect_git_diff_pattern(tmp_path: Path) -> None:
    """验收员应通过 git_diff 工具自行查看未暂存变更。"""
    _init_test_repo(tmp_path)
    (tmp_path / "notes.txt").write_text("v1", encoding="utf-8")
    _run_git(["add", "."], tmp_path)
    _run_git(["commit", "-m", "initial"], tmp_path)

    (tmp_path / "notes.txt").write_text("v2-unstaged", encoding="utf-8")
    (tmp_path / "staged.txt").write_text("staged-only", encoding="utf-8")
    _run_git(["add", "staged.txt"], tmp_path)

    unstaged = git_tools_mod.git_diff(str(tmp_path))
    staged = _run_git(["diff", "--cached"], tmp_path)

    assert "v2-unstaged" in unstaged
    assert "staged-only" in staged
    assert "exit_code: 0" in unstaged


def _init_test_repo(path: Path) -> None:
    """初始化测试用 git 仓库并配置用户信息。"""
    _run_git(["init"], path)
    _run_git(["config", "user.name", "test"], path)
    _run_git(["config", "user.email", "test@test.com"], path)


def _run_git(args: list[str], cwd: Path) -> str:
    """在指定目录中执行 git 命令，返回合并输出。"""
    completed = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    parts: list[str] = []
    if completed.stdout.strip():
        parts.append(completed.stdout.rstrip("\n"))
    if completed.stderr.strip():
        parts.append(completed.stderr.rstrip("\n"))
    parts.append(f"exit_code: {completed.returncode}")
    return "\n".join(parts)
