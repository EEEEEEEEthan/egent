"""Git 命令内置工具。"""

from __future__ import annotations

import subprocess
from pathlib import Path

import egent.builtin_tools.command_utils

__all__ = [
    "git_init",
    "git_clone",
    "git_status",
    "git_add",
    "git_commit",
    "git_push",
    "git_pull",
    "git_fetch",
    "git_checkout",
    "git_branch",
    "git_log",
    "git_diff",
    "git_merge",
    "git_remote",
    "git_reset",
    "git_stash",
    "git_clean",
    "git_tag",
    "read_only_tools",
    "write_only_tools",
]


def _run_git(args: list[str], working_directory: str | None = None) -> str:
    """执行 git 命令，统一处理错误和超时。"""
    cmd = ["git"] + args
    resolved_directory = (
        Path.cwd() if working_directory is None else Path(working_directory).resolve()
    )
    if not resolved_directory.is_dir():
        raise FileNotFoundError(f"目录不存在：{working_directory}")
    try:
        completed = subprocess.run(
            cmd,
            cwd=resolved_directory,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except subprocess.TimeoutExpired as timeout_error:
        raise TimeoutError("git 命令执行超时（30s）") from timeout_error
    return egent.builtin_tools.command_utils.format_command_result(
        completed.stdout, completed.stderr, completed.returncode
    )


def git_init(path: str | None = None) -> str:
    """初始化一个新的 Git 仓库。

    @param path 仓库路径，缺省为当前工作目录
    """
    target = path or "."
    return _run_git(["init", target])


def git_clone(url: str, path: str | None = None) -> str:
    """克隆远程仓库到本地。

    @param url 远程仓库地址
    @param path 克隆目标路径，缺省使用仓库名
    """
    args = ["clone", url]
    if path is not None:
        args.append(path)
    return _run_git(args)


def git_status(path: str | None = None) -> str:
    """查看工作区状态（精简格式）。

    @param path 仓库目录路径，缺省为当前工作目录
    """
    return _run_git(["status", "--porcelain"], path)


def git_add(paths: str, path: str | None = None) -> str:
    """暂存文件变更。

    @param paths 要暂存的文件，支持空格分隔多个路径
    @param path 仓库目录路径，缺省为当前工作目录
    """
    args = ["add"] + paths.split()
    return _run_git(args, path)


def git_commit(message: str, path: str | None = None) -> str:
    """提交暂存区变更。

    @param message 提交信息
    @param path 仓库目录路径，缺省为当前工作目录
    """
    return _run_git(["commit", "-m", message], path)


def git_push(
    remote: str = "origin",
    branch: str | None = None,
    path: str | None = None,
) -> str:
    """推送本地提交到远程仓库。

    @param remote 远程仓库名称，缺省 "origin"
    @param branch 要推送的分支名，缺省为当前分支
    @param path 仓库目录路径，缺省为当前工作目录
    """
    args = ["push", remote]
    if branch is not None:
        args.append(branch)
    return _run_git(args, path)


def git_pull(
    remote: str = "origin",
    branch: str | None = None,
    path: str | None = None,
) -> str:
    """从远程仓库拉取并合并。

    @param remote 远程仓库名称，缺省 "origin"
    @param branch 要拉取的分支名，缺省为当前分支
    @param path 仓库目录路径，缺省为当前工作目录
    """
    args = ["pull", remote]
    if branch is not None:
        args.append(branch)
    return _run_git(args, path)


def git_fetch(
    remote: str = "origin",
    path: str | None = None,
) -> str:
    """从远程仓库获取最新数据但不合并。

    @param remote 远程仓库名称，缺省 "origin"
    @param path 仓库目录路径，缺省为当前工作目录
    """
    return _run_git(["fetch", remote], path)


def git_checkout(
    target: str,
    create_branch: bool = False,
    path: str | None = None,
) -> str:
    """切换分支或还原文件。

    @param target 目标分支名、commit 或 tag
    @param create_branch 是否创建新分支（-b），缺省 False
    @param path 仓库目录路径，缺省为当前工作目录
    """
    args = ["checkout"]
    if create_branch:
        args.append("-b")
    args.append(target)
    return _run_git(args, path)


def git_branch(path: str | None = None) -> str:
    """列出所有本地分支。

    @param path 仓库目录路径，缺省为当前工作目录
    """
    return _run_git(["branch"], path)


def git_log(
    count: int = 20,
    oneline: bool = True,
    path: str | None = None,
) -> str:
    """查看提交历史。

    @param count 显示最近提交数量，缺省 20
    @param oneline 是否单行显示，缺省 True
    @param path 仓库目录路径，缺省为当前工作目录
    """
    args = ["log", f"-{count}"]
    if oneline:
        args.append("--oneline")
    return _run_git(args, path)


def git_diff(path: str | None = None) -> str:
    """显示未暂存的更改差异。

    @param path 仓库目录路径，缺省为当前工作目录
    """
    return _run_git(["diff"], path)


def git_merge(branch: str, path: str | None = None) -> str:
    """合并指定分支到当前分支。

    @param branch 要合并的分支名
    @param path 仓库目录路径，缺省为当前工作目录
    """
    return _run_git(["merge", branch], path)


def git_remote(path: str | None = None) -> str:
    """列出远程仓库。

    @param path 仓库目录路径，缺省为当前工作目录
    """
    return _run_git(["remote", "-v"], path)


def git_reset(
    target: str = "HEAD",
    hard: bool = False,
    path: str | None = None,
) -> str:
    """重置当前 HEAD 到指定状态。

    @param target 目标 commit/tag/引用，缺省 "HEAD"
    @param hard 是否硬重置（丢弃所有更改），缺省 False
    @param path 仓库目录路径，缺省为当前工作目录
    """
    args = ["reset"]
    if hard:
        args.append("--hard")
    args.append(target)
    return _run_git(args, path)


def git_stash(action: str = "list", path: str | None = None) -> str:
    """管理暂存工作区（stash）。

    @param action 操作类型：list/push/pop/drop/apply，缺省 "list"
    @param path 仓库目录路径，缺省为当前工作目录
    """
    valid_actions = {"list", "push", "pop", "drop", "apply"}
    if action not in valid_actions:
        raise ValueError(
            f"无效的 stash 操作 '{action}'，"
            f"支持的操作：{', '.join(sorted(valid_actions))}"
        )
    args = ["stash", action] if action != "list" else ["stash", "list"]
    return _run_git(args, path)


def git_clean(
    directories: bool = True,
    dry_run: bool = False,
    path: str | None = None,
) -> str:
    """清理未跟踪的文件与目录。

    @param directories 是否同时删除未跟踪目录（-d），缺省 True
    @param dry_run 仅预览将删除的内容不实际删除（-n），缺省 False
    @param path 仓库目录路径，缺省为当前工作目录
    """
    args = ["clean"]
    if dry_run:
        args.append("-n")
    else:
        args.append("-f")
    if directories:
        args.append("-d")
    return _run_git(args, path)


def git_tag(path: str | None = None) -> str:
    """列出所有标签。

    @param path 仓库目录路径，缺省为当前工作目录
    """
    return _run_git(["tag"], path)


read_only_tools: list = [
    git_status,
    git_branch,
    git_log,
    git_diff,
    git_remote,
    git_tag,
]

write_only_tools: list = [
    git_init,
    git_clone,
    git_add,
    git_commit,
    git_push,
    git_pull,
    git_fetch,
    git_checkout,
    git_merge,
    git_reset,
    git_stash,
    git_clean,
]
