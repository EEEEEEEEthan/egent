"""examples 共享辅助代码。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import override

import egent.builtin_tools.path_validator
import egent.conversation
import egent.tool

_SENSITIVE_PATTERNS: tuple[str, ...] = (
    "**/.model.toml",
)

_SEARCH_EXCLUDED_PATTERNS: tuple[str, ...] = (
    ".egent/.temp",
    "**/.model.toml",
    "**/.git",
    "**/*.pyc",
    "**/.pytest_cache",
    "**/.ruff_cache",
    "**/__pycache__",
)


def _matches_path_patterns(relative_text: str, patterns: tuple[str, ...]) -> bool:
    path_segments = PurePosixPath(relative_text).parts
    for segment_count in range(1, len(path_segments) + 1):
        path_prefix = PurePosixPath(*path_segments[:segment_count])
        if any(path_prefix.full_match(pattern) for pattern in patterns):
            return True
    return False


class EgentPathValidator(egent.builtin_tools.path_validator.PathValidator):
    """示例用路径校验：cwd 内可发现，敏感文件禁读写，搜索排除噪声路径。"""

    def _relative_posix(self, path: Path) -> str | None:
        try:
            return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
        except ValueError:
            return None

    def _is_sensitive(self, path: Path) -> bool:
        relative_text = self._relative_posix(path)
        if relative_text is None:
            return False
        return _matches_path_patterns(relative_text, _SENSITIVE_PATTERNS)

    def _is_search_excluded(self, path: Path) -> bool:
        relative_text = self._relative_posix(path)
        if relative_text is None:
            return True
        return _matches_path_patterns(relative_text, _SEARCH_EXCLUDED_PATTERNS)

    @override
    def _is_discoverable(self, path: Path) -> bool:
        return self._relative_posix(path) is not None

    @override
    def _is_readable(self, path: Path) -> bool:
        return self._relative_posix(path) is not None and not self._is_sensitive(path)

    @override
    def _is_editable(self, path: Path) -> bool:
        return self._relative_posix(path) is not None and not self._is_sensitive(path)

    @override
    def _is_searchable(self, path: Path) -> bool:
        return self._relative_posix(path) is not None and not self._is_search_excluded(path)


def print_stream_event(event: object) -> None:
    """将对话流事件打印到终端。"""
    if isinstance(event, egent.conversation.TextDelta):
        print(event.text, end="", flush=True)
    elif isinstance(event, egent.conversation.ToolCallStarted):
        print(f"\n[tool_call: {event.name}]", flush=True)


async def request_and_print(
    conversation: egent.conversation.Conversation,
    tools: Iterable[egent.tool.ToolCallable],
) -> None:
    """执行一轮工具调用请求并打印流式输出。"""
    async for event in conversation.request(tools=tools):
        print_stream_event(event)
    print()


async def request_until_submit_and_print(
    conversation: egent.conversation.Conversation,
    submit_tool: egent.tool.ToolCallable,
    tools: Iterable[egent.tool.ToolCallable],
) -> None:
    """循环请求直至 submit 工具被调用，并打印流式输出。"""
    async for event in conversation.request_until_submit(submit_tool, tools):
        print_stream_event(event)
    print()


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
