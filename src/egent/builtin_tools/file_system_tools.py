"""文件系统内置工具（读取与编辑）。"""
# pylint: disable=protected-access

from __future__ import annotations

import fnmatch
import logging
import re
import shutil
import time
import traceback
from collections.abc import Callable, Generator
from dataclasses import dataclass
from pathlib import Path

import egent._line_position
import egent.builtin_tools.path_validator
import egent._constants
import egent.tool

_logger = logging.getLogger(__name__)

__all__ = ["FileSystemToolSet"]


@dataclass
class FileSystemToolSet:
    """基于同一路径权限配置的文件系统工具集。"""

    path_permissions: egent.builtin_tools.path_validator.PathPermissions | None = None

    def list_path_permissions(self) -> str:
        """列出当前路径权限规则（可发现、可读、可编辑的白名单与黑名单）"""
        if self.path_permissions is None:
            return "路径权限未配置，所有路径均可访问。"
        return self.path_permissions.format_rules()

    def walk_files(
        self,
        directory: str,
        depth: int | None = None,
    ) -> str:
        """遍历目录文件树并输出所有文件名

        @param directory 需要遍历的文件夹路径(如果填相对路径将以当前工作目录为基准)
        @param depth 最大层级深度，0 表示不限制，缺省 1
        """
        root = self._open_directory(directory)
        max_depth = depth if depth is not None else 1
        lines: list[str] = []

        def walk_directory(
            directory_path: Path,
            ancestor_is_last_flags: tuple[bool, ...] = (),
        ) -> None:
            if 0 < max_depth <= len(ancestor_is_last_flags):
                return
            try:
                entries = sorted(
                    directory_path.iterdir(),
                    key=lambda path: (not path.is_dir(), path.name.lower()),
                )
            except OSError as os_error:
                raise OSError(f"无法访问 {directory_path}：{os_error}") from os_error
            visible_entries = [
                entry_path
                for entry_path in entries
                if self.path_permissions is None
                or self.path_permissions.is_discoverable(entry_path.resolve())
            ]
            for index, entry_path in enumerate(visible_entries):
                is_last_entry = index == len(visible_entries) - 1
                is_symlink = entry_path.is_symlink()
                is_directory = entry_path.is_dir(follow_symlinks=False) or is_symlink
                prefix = "".join(
                    " " if ancestor_is_last else "│"
                    for ancestor_is_last in ancestor_is_last_flags
                )
                connector = "└" if is_last_entry else "├"
                display_name = f"{entry_path.name}/" if is_directory else entry_path.name
                if is_symlink:
                    display_name += " #symlink"
                lines.append(prefix + connector + display_name)
                if is_directory:
                    walk_directory(entry_path, ancestor_is_last_flags + (is_last_entry,))

        walk_directory(root)
        return "(空目录)" if not lines else "\n".join(lines)

    def search_directory(
        self,
        pattern: str,
        directory: str = ".",
        file_filter: str | None = None,
    ) -> str:
        """在指定目录中深度优先遍历，按正则表达式逐行搜索文件内容（仅搜索可发现且可读的文件）

        @param pattern 正则表达式
        @param directory 搜索目录.如果填相对路径将以当前工作目录为基准.缺省 '.'
        @param file_filter 文件名 glob 过滤，如 '*.py'
        """
        try:
            regex = re.compile(pattern)
        except re.error as regex_error:
            raise ValueError(f"无效的正则表达式：{regex_error}") from regex_error
        root = self._open_directory(directory)
        deadline_monotonic = (
            time.monotonic() + egent._constants.SEARCH_DIRECTORY_TIMEOUT_SECONDS
        )
        matched_lines: list[str] = []
        timed_out = False

        def visit_directory(directory_path: Path) -> None:
            nonlocal timed_out
            if timed_out or time.monotonic() >= deadline_monotonic:
                timed_out = True
                return
            try:
                entries = sorted(
                    directory_path.iterdir(),
                    key=lambda entry_path: (not entry_path.is_dir(), entry_path.name.lower()),
                )
            except OSError:
                _logger.error("访问目录失败 %s:\n%s", directory_path, traceback.format_exc().rstrip())
                return
            for entry_path in entries:
                if timed_out or time.monotonic() >= deadline_monotonic:
                    timed_out = True
                    return
                if entry_path.is_symlink():
                    continue
                resolved_entry_path = entry_path.resolve()
                if not resolved_entry_path.is_relative_to(root):
                    continue
                if (
                    self.path_permissions is not None
                    and not self.path_permissions.is_discoverable(resolved_entry_path)
                ):
                    continue
                if entry_path.is_dir():
                    visit_directory(entry_path)
                    continue
                if not entry_path.is_file():
                    continue
                if (
                    self.path_permissions is not None
                    and not self.path_permissions.is_readable(resolved_entry_path)
                ):
                    continue
                if file_filter is not None and not fnmatch.fnmatch(entry_path.name, file_filter):
                    continue
                relative_path_label = resolved_entry_path.relative_to(root).as_posix()
                file_deadline_monotonic = min(
                    time.monotonic() + egent._constants.SEARCH_FILE_TIMEOUT_SECONDS,
                    deadline_monotonic,
                )
                file_matches, file_timed_out = self._collect_search_matches(
                    resolved_entry_path,
                    regex,
                    file_deadline_monotonic,
                    lambda line_number, line_text, path_label=relative_path_label: (
                        f"[{path_label} line{line_number}] {line_text}"
                    ),
                )
                matched_lines.extend(file_matches)
                if file_timed_out:
                    timed_out = True
                    return

        visit_directory(root)
        return self._format_search_result(matched_lines, timed_out)

    def search_file(
        self,
        pattern: str,
        path: str,
    ) -> str:
        """在指定文件中按正则表达式流式逐行搜索并输出（仅搜索可读文件）

        @param pattern 正则表达式
        @param path 文件路径.如果填相对路径将以当前工作目录为基准
        """
        try:
            regex = re.compile(pattern)
        except re.error as regex_error:
            raise ValueError(f"无效的正则表达式：{regex_error}") from regex_error
        resolved = egent.builtin_tools.path_validator.resolve_path(path)
        if not resolved.is_file():
            raise FileNotFoundError(f"文件不存在：{path}")
        if self.path_permissions is not None and not self.path_permissions.is_readable(resolved):
            raise PermissionError(f"没有权限搜索文件：{path}")
        deadline_monotonic = time.monotonic() + egent._constants.SEARCH_FILE_TIMEOUT_SECONDS
        matched_lines, timed_out = self._collect_search_matches(
            resolved,
            regex,
            deadline_monotonic,
            lambda line_number, line_text: f"[line{line_number}] {line_text}",
        )
        return self._format_search_result(matched_lines, timed_out)

    def read_file(
        self,
        path: str,
        line: int | None = None,
        column: int | None = None,
        limit: int | None = None,
    ) -> str:
        """读取指定文件内容.请优先使用 read_file_with_outline 读取大纲,然后再 read_file 读取细节.

        @param path 文件路径,如果填相对路径将以当前工作目录为基准
        @param line 起始行号，从 1 开始，缺省 1
        @param column 起始列号，从 1 开始，缺省 1
        @param limit 读取行数，缺省读取到文件末尾
        """
        _, text = self._read_utf8_file(
            path,
            lambda path_validator, resolved_path: path_validator.is_readable(resolved_path),
        )
        file_lines = text.splitlines(keepends=True)
        start_line = line or 1
        start_column = column or 1
        content = self._slice_lines_from_position(file_lines, start_line, start_column, limit)
        if not content:
            return "(空文件)"
        # 文件在磁盘上，AI 可用 line/column 续读；降低阈值避免读临时文件循环。
        max_chars = egent._constants.TOOL_RESULT_MAX_CHARS * 9 // 10
        if len(content) <= max_chars:
            return content
        next_line, next_column = egent._line_position.position_after_characters(
            file_lines,
            start_line,
            start_column,
            max_chars,
        )
        return (
            f"{content[:max_chars]}...\n"
            f"(内容太长被截断，剩余{len(content) - max_chars}字符，"
            f"请用 line={next_line} column={next_column} 继续读取)"
        )

    def create_file(self, path: str, content: str) -> str:
        """创建新文件

        @param path 文件路径（如果填相对路径将以当前工作目录为基准）
        @param content 文件内容
        """
        resolved_path = self._resolve_editable_path(path)
        if resolved_path.is_file():
            raise FileExistsError(f"文件已存在：{path}")
        if not resolved_path.parent.is_dir():
            raise FileNotFoundError(f"父目录不存在：{path}")
        resolved_path.write_text(content, encoding="utf-8")
        return f"已创建文件：{resolved_path}"

    def append_text(self, path: str, text: str) -> str:
        """向文件追加文本

        @param path 文件路径（如果填相对路径将以当前工作目录为基准）
        @param text 要追加的文本
        """
        resolved_path = self._open_existing_editable_file(path)
        with resolved_path.open("a", encoding="utf-8") as file_handle:
            file_handle.write(text)
        return f"已追加写入：{resolved_path}"

    def apply_patch(
        self,
        path: str,
        old_string: str,
        new_string: str,
    ) -> str:
        """按精确文本匹配替换文件内容，old_string 必须唯一匹配

        @param path 文件路径（如果填相对路径将以当前工作目录为基准）
        @param old_string 要被替换的原文本，需与文件内容完全一致且仅匹配一处
        @param new_string 替换后的文本
        """
        resolved_path, original_text = self._read_utf8_file(
            path,
            lambda path_validator, resolved_path: path_validator.is_editable(resolved_path),
        )
        match_count = original_text.count(old_string)
        if match_count == 0:
            raise ValueError(f"未找到要替换的文本：{path}")
        if match_count != 1:
            raise ValueError(f"找到 {match_count} 处匹配，请提供更多上下文：{path}")
        updated_text = original_text.replace(old_string, new_string, 1)
        resolved_path.write_text(updated_text, encoding="utf-8")
        return f"已应用补丁：{resolved_path}"

    def replace(self, path: str, pattern: str, replacement: str) -> str:
        """对文件内容执行正则表达式全量替换

        @param path 文件路径（如果填相对路径将以当前工作目录为基准）
        @param pattern 正则表达式
        @param replacement 替换文本
        """
        resolved_path, original_text = self._read_utf8_file(
            path,
            lambda path_validator, resolved_path: path_validator.is_editable(resolved_path),
        )
        try:
            regex = re.compile(pattern)
        except re.error as regex_error:
            raise ValueError(f"无效的正则表达式：{regex_error}") from regex_error
        updated_text, match_count = regex.subn(replacement, original_text)
        if match_count == 0:
            return f"已替换 0 处：{resolved_path}"
        resolved_path.write_text(updated_text, encoding="utf-8")
        return f"已替换 {match_count} 处：{resolved_path}"

    def rewrite(self, path: str, content: str) -> str:
        """重新写入整个文件（覆盖已有或创建新文件）

        @param path 文件路径（如果填相对路径将以当前工作目录为基准）
        @param content 文件内容
        """
        resolved_path = self._resolve_editable_path(path)
        if not resolved_path.parent.is_dir():
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_path.write_text(content, encoding="utf-8")
        return f"已写入文件：{resolved_path}"

    def delete(self, path: str) -> str:
        """删除文件或目录（递归删除目录）

        @param path 文件或目录路径（如果填相对路径将以当前工作目录为基准）
        """
        resolved_path = self._resolve_editable_path(path)
        if not resolved_path.exists():
            raise FileNotFoundError(f"路径不存在：{path}")
        if resolved_path.is_file():
            resolved_path.unlink()
            return f"已删除文件：{resolved_path}"
        if resolved_path.is_dir():
            shutil.rmtree(resolved_path)
            return f"已删除目录：{resolved_path}"
        raise ValueError(f"路径不是文件也不是目录：{path}")

    def outline(self, path: str) -> str:
        """解析文件大纲,目前暂时支持.cs, .gd, .md, .py文件.

        @param path 文件路径（如果填相对路径将以当前工作目录为基准）
        """
        import importlib  # pylint: disable=import-outside-toplevel
        resolved = egent.builtin_tools.path_validator.resolve_path(path)
        if not resolved.is_file():
            raise FileNotFoundError(f"文件不存在：{path}")
        if self.path_permissions is not None and not self.path_permissions.is_readable(resolved):
            raise PermissionError(f"没有权限读取文件：{path}")
        if (
            parser_cls := importlib.import_module(
                "egent.builtin_tools.outline_tools"
            ).get_parser(resolved.suffix)
        ) is None:
            return "不支持的文件类型"
        return parser_cls().parse(self._read_utf8_text(resolved, path))

    @property
    def read_tools(self) -> tuple[
        egent.tool.ToolCallable,
        egent.tool.ToolCallable,
        egent.tool.ToolCallable,
        egent.tool.ToolCallable,
        egent.tool.ToolCallable,
        egent.tool.ToolCallable,
    ]:
        """读取类工具（权限列表、遍历、读取、目录搜索、文件搜索、大纲解析）。"""
        return (
            self.list_path_permissions,
            self.walk_files,
            self.read_file,
            self.search_directory,
            self.search_file,
            self.outline,
        )

    @property
    def edit_tools(self) -> tuple[
        egent.tool.ToolCallable,
        egent.tool.ToolCallable,
        egent.tool.ToolCallable,
        egent.tool.ToolCallable,
        egent.tool.ToolCallable,
        egent.tool.ToolCallable,
    ]:
        """编辑类工具（创建、追加、编辑、替换、重写、删除）。"""
        return (
            self.create_file,
            self.append_text,
            self.apply_patch,
            self.replace,
            self.rewrite,
            self.delete,
        )

    @property
    def tools(self) -> tuple[egent.tool.ToolCallable, ...]:
        """全部文件系统工具。"""
        return self.read_tools + self.edit_tools

    @staticmethod
    def _read_utf8_text(resolved_path: Path, path_label: str) -> str:
        if not resolved_path.is_file():
            raise FileNotFoundError(f"文件不存在：{path_label}")
        try:
            return resolved_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as decode_error:
            raise ValueError(f"无法以 UTF-8 解码文件：{path_label}") from decode_error

    def _read_utf8_file(
        self,
        path_text: str,
        may_access: Callable[
            [egent.builtin_tools.path_validator.PathPermissions, Path],
            bool,
        ],
    ) -> tuple[Path, str]:
        resolved_path = egent.builtin_tools.path_validator.resolve_path(path_text)
        if self.path_permissions is not None and not may_access(
            self.path_permissions,
            resolved_path,
        ):
            raise PermissionError(f"没有权限访问路径：{path_text}")
        return resolved_path, self._read_utf8_text(resolved_path, path_text)

    def _resolve_editable_path(self, path_text: str) -> Path:
        resolved_path = egent.builtin_tools.path_validator.resolve_path(path_text)
        if self.path_permissions is not None and not self.path_permissions.is_editable(
            resolved_path,
        ):
            raise PermissionError(f"没有权限访问路径：{path_text}")
        return resolved_path

    def _open_existing_editable_file(self, path_text: str) -> Path:
        resolved_path = self._resolve_editable_path(path_text)
        if not resolved_path.is_file():
            raise FileNotFoundError(f"文件不存在：{path_text}")
        return resolved_path

    def _open_directory(self, directory_text: str) -> Path:
        directory_input = directory_text or "."
        root = egent.builtin_tools.path_validator.resolve_path(directory_input)
        if self.path_permissions is not None and not self.path_permissions.is_discoverable(root):
            raise PermissionError(f"没有权限：{directory_input}")
        if not root.is_dir():
            raise FileNotFoundError(f"目录不存在：{directory_input}")
        return root

    @staticmethod
    def _slice_lines_from_position(
        file_lines: list[str],
        start_line: int,
        start_column: int,
        line_limit: int | None,
    ) -> str:
        start_line_index = max(start_line - 1, 0)
        if start_line_index >= len(file_lines):
            return ""
        end_line_index = (
            start_line_index + line_limit
            if line_limit is not None
            else len(file_lines)
        )
        end_line_index = min(end_line_index, len(file_lines))
        if end_line_index <= start_line_index:
            return ""
        first_line_fragment = file_lines[start_line_index][max(start_column - 1, 0) :]
        if end_line_index == start_line_index + 1:
            return first_line_fragment
        return first_line_fragment + "".join(file_lines[start_line_index + 1 : end_line_index])

    @staticmethod
    def _format_search_result(matched_lines: list[str], timed_out: bool) -> str:
        body = "\n".join(matched_lines) if matched_lines else "(无匹配)"
        if timed_out:
            return f"(搜索超时)\n{body}"
        return body

    @staticmethod
    def _iter_matching_file_lines(
        resolved_path: Path,
        regex: re.Pattern[str],
        deadline_monotonic: float,
    ) -> Generator[tuple[int, str], None, bool]:
        try:
            with resolved_path.open(encoding="utf-8") as file_handle:
                for line_number, raw_line in enumerate(file_handle, start=1):
                    if time.monotonic() >= deadline_monotonic:
                        return True
                    line_text = raw_line.rstrip("\r\n")
                    if regex.search(line_text):
                        yield line_number, line_text
        except (UnicodeDecodeError, OSError):
            _logger.error("读取文件失败 %s:\n%s", resolved_path, traceback.format_exc().rstrip())
            return False
        return False

    @classmethod
    def _collect_search_matches(
        cls,
        resolved_path: Path,
        regex: re.Pattern[str],
        deadline_monotonic: float,
        format_match: Callable[[int, str], str],
    ) -> tuple[list[str], bool]:
        matched_lines: list[str] = []
        matching_lines = cls._iter_matching_file_lines(
            resolved_path,
            regex,
            deadline_monotonic,
        )
        timed_out = False
        try:
            while True:
                line_number, line_text = next(matching_lines)
                matched_lines.append(format_match(line_number, line_text))
        except StopIteration as stop_iteration:
            timed_out = bool(stop_iteration.value)
        return matched_lines, timed_out
