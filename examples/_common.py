"""examples 共享辅助代码。"""

from __future__ import annotations

import asyncio
import dataclasses
from collections.abc import Awaitable, Callable

import egent.builtin_tools.path_validator

_SENSITIVE_PATTERNS: tuple[str, ...] = (
    "**/.model.toml",
)

_DISCOVERABLE_BLACKLIST_PATTERNS: tuple[str, ...] = (
    "**/.git",
    "**/*.pyc",
    "**/.pytest_cache",
    "**/.ruff_cache",
    "**/__pycache__",
)

_READABLE_BLACKLIST_PATTERNS: tuple[str, ...] = _SENSITIVE_PATTERNS


def create_egent_path_permissions() -> egent.builtin_tools.path_validator.PathPermissions:
    """示例用路径权限：工作目录内可发现，敏感文件禁读写，噪声路径不可发现。"""
    return egent.builtin_tools.path_validator.PathPermissions(
        discoverable=egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=("**",),
            blacklist=_DISCOVERABLE_BLACKLIST_PATTERNS,
        ),
        readable=egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=("**",),
            blacklist=_READABLE_BLACKLIST_PATTERNS,
        ),
        editable=egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=("**",),
            blacklist=_READABLE_BLACKLIST_PATTERNS,
        ),
    )


def create_read_only_egent_path_permissions() -> egent.builtin_tools.path_validator.PathPermissions:
    """示例用只读路径权限：可发现可读，全部路径不可编辑。"""
    base = create_egent_path_permissions()
    return dataclasses.replace(
        base,
        editable=egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=(),
            blacklist=(),
        ),
    )


def reload_modules() -> str:  # pylint: disable=import-outside-toplevel
    """重新加载所有 egent 项目模块（egent.* / _common / example_*），使代码更改立即生效。

    按依赖顺序 reload：先 ``egent.*``（底层依赖），再 ``_common`` 和 ``example_*``（上层）。

    Returns:
        重新加载结果汇总，包含成功/失败数量及模块列表。
    """
    import importlib  # pylint: disable=import-outside-toplevel
    import sys  # pylint: disable=import-outside-toplevel

    egent_modules: list[str] = []
    other_modules: list[str] = []
    for mod_name in list(sys.modules):
        if mod_name.startswith("egent.") or mod_name == "egent":
            egent_modules.append(mod_name)
        elif mod_name == "_common" or mod_name.startswith("example_"):
            other_modules.append(mod_name)

    # 按依赖顺序：先 egent.*，再 _common 和 example_*
    sorted_names = sorted(egent_modules) + sorted(other_modules)

    success: list[str] = []
    failed: list[str] = []
    for mod_name in sorted_names:
        try:
            importlib.reload(sys.modules[mod_name])
            success.append(mod_name)
        except Exception:  # pylint: disable=broad-exception-caught
            failed.append(mod_name)

    lines: list[str] = []
    lines.append(f"重新加载完成：成功 {len(success)} 个，失败 {len(failed)} 个。")
    if success:
        lines.append(f"成功模块：{', '.join(success)}")
    if failed:
        lines.append(f"失败模块：{', '.join(failed)}")
    return "\n".join(lines)


def run_cli(async_main: Callable[[], Awaitable[int]]) -> None:
    """运行 async_main 并以其返回值作为进程退出码。"""
    raise SystemExit(asyncio.run(async_main()))
