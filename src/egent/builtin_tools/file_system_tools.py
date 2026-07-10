"""文件系统内置工具（读取与编辑）。"""

from __future__ import annotations

import fnmatch
import re
import shutil
from collections.abc import Callable
from pathlib import Path

import egent._line_position
import egent.builtin_tools.path_validator
import egent.limits
import egent.tool

__all__ = [
    "get_append_text_tool",
    "get_apply_patch_tool",
    "get_create_file_tool",
    "get_delete_tool",
    "get_edit_tools",
    "get_file_tools",
    "get_read_file_tool",
    "get_list_path_permissions_tool",
    "get_read_tools",
    "get_replace_tool",
    "get_rewrite_tool",
    "get_search_directory_tool",
    "get_search_file_tool",
    "get_tools",
    "get_walk_files_tool",
]


def _read_utf8_text(resolved_path: Path, path_label: str) -> str:
    if not resolved_path.is_file():
        raise FileNotFoundError(f"文件不存在：{path_label}")
    try:
        return resolved_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as decode_error:
        raise ValueError(f"无法以 UTF-8 解码文件：{path_label}") from decode_error


def _read_utf8_file(
    path_text: str,
    validator: egent.builtin_tools.path_validator.PathPermissions | None,
    may_access: Callable[[egent.builtin_tools.path_validator.PathPermissions, Path], bool],
) -> tuple[Path, str]:
    resolved_path = egent.builtin_tools.path_validator.resolve_path(path_text)
    if validator is not None and not may_access(validator, resolved_path):
        raise PermissionError(f"没有权限访问路径：{path_text}")
    return resolved_path, _read_utf8_text(resolved_path, path_text)


def _resolve_scoped_path(
    path_text: str,
    validator: egent.builtin_tools.path_validator.PathPermissions | None,
) -> Path:
    resolved_path = egent.builtin_tools.path_validator.resolve_path(path_text)
    if validator is not None and not validator.is_editable(resolved_path):
        raise PermissionError(f"没有权限访问路径：{path_text}")
    return resolved_path


def _open_existing_file(
    path_text: str,
    validator: egent.builtin_tools.path_validator.PathPermissions | None,
) -> Path:
    resolved_path = _resolve_scoped_path(path_text, validator)
    if not resolved_path.is_file():
        raise FileNotFoundError(f"文件不存在：{path_text}")
    return resolved_path


def _open_directory(
    directory_text: str,
    validator: egent.builtin_tools.path_validator.PathPermissions | None,
) -> Path:
    directory_input = directory_text or "."
    root = egent.builtin_tools.path_validator.resolve_path(directory_input)
    if validator is not None and not validator.is_discoverable(root):
        raise PermissionError(f"没有权限：{directory_input}")
    if not root.is_dir():
        raise FileNotFoundError(f"目录不存在：{directory_input}")
    return root


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


def get_walk_files_tool(
    validator: egent.builtin_tools.path_validator.PathPermissions | None = None,
    name: str = "walk_files",
    description: str | None = None,
) -> egent.tool.ToolCallable:
    """生成预配置的目录遍历工具。"""
    working_directory = Path.cwd()
    tool_description = description or "遍历目录文件树并输出所有文件名"

    def walk_files(
        directory: str,
        depth: int | None = None,
    ) -> str:
        root = _open_directory(directory, validator)
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
                    key=lambda path: (not path.is_dir(), path.name.lower())
                )
            except OSError as os_error:
                raise OSError(f"无法访问 {directory_path}：{os_error}") from os_error
            visible_entries = [
                entry_path
                for entry_path in entries
                if validator is None or validator.is_discoverable(entry_path.resolve())
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

    walk_files.__name__ = name
    walk_files.__doc__ = (
        f"{tool_description}\n\n"
        f"@param directory 需要遍历的文件夹路径(如果填相对路径将以工作目录 {working_directory} 为基准)\n"
        "@param depth 最大层级深度，0 表示不限制，缺省 1"
    )
    return walk_files


def _search_file_content(
    resolved: Path,
    regex: re.Pattern,
    validator: egent.builtin_tools.path_validator.PathPermissions | None,
    path_label: str,
) -> str:
    """在单个可读文件中搜索正则匹配行并返回格式化结果。"""
    if validator is not None and not validator.is_readable(resolved):
        raise PermissionError(f"没有权限搜索文件：{path_label}")
    try:
        text = resolved.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return "(无匹配)"
    lines: list[str] = []
    file_name = resolved.name
    for line_number, line_text in enumerate(text.splitlines(), start=1):
        if regex.search(line_text):
            lines.append(f"[{file_name} line{line_number}] {line_text}")
    if not lines:
        return "(无匹配)"
    return "\n".join(lines)


def _search_directory(
    directory: str,
    regex: re.Pattern,
    validator: egent.builtin_tools.path_validator.PathPermissions | None,
    file_filter: str | None,
) -> str:
    """在目录中递归搜索文件内容和文件名匹配。"""
    root = _open_directory(directory, validator)
    lines: list[str] = []
    for file_path in sorted(root.rglob("*"), key=lambda path: path.as_posix().lower()):
        if not file_path.is_file():
            continue
        resolved_file_path = file_path.resolve()
        if not resolved_file_path.is_relative_to(root):
            continue
        if validator is not None and not validator.is_searchable(resolved_file_path):
            continue
        if file_filter is not None and not fnmatch.fnmatch(file_path.name, file_filter):
            continue
        relative_file_text = resolved_file_path.relative_to(root).as_posix()
        if regex.search(relative_file_text):
            lines.append(f"[{relative_file_text}]")
        try:
            text = resolved_file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line_text in enumerate(text.splitlines(), start=1):
            if regex.search(line_text):
                lines.append(f"[{relative_file_text} line{line_number}] {line_text}")
    if not lines:
        return "(无匹配)"
    return "\n".join(lines)


def get_search_directory_tool(
    validator: egent.builtin_tools.path_validator.PathPermissions | None = None,
    name: str = "search_directory",
    description: str | None = None,
) -> egent.tool.ToolCallable:
    """生成预配置的目录搜索工具（仅搜索可发现且可读的文件）。"""
    working_directory = Path.cwd()
    tool_description = description or (
        "在指定目录中按正则表达式逐行搜索文件或文件名并输出（仅搜索可发现且可读的文件）"
    )

    def search_directory(
        pattern: str,
        directory: str = ".",
        file_filter: str | None = None,
    ) -> str:
        try:
            regex = re.compile(pattern)
        except re.error as regex_error:
            raise ValueError(f"无效的正则表达式：{regex_error}") from regex_error
        return _search_directory(directory, regex, validator, file_filter)

    search_directory.__name__ = name
    search_directory.__doc__ = (
        f"{tool_description}\n\n"
        "@param pattern 正则表达式\n"
        f"@param directory 搜索目录.如果填相对路径将以工作目录 {working_directory} 为基准.缺省 '.'\n"
        "@param file_filter 文件名 glob 过滤，如 '*.py'"
    )
    return search_directory


def get_search_file_tool(
    validator: egent.builtin_tools.path_validator.PathPermissions | None = None,
    name: str = "search_file",
    description: str | None = None,
) -> egent.tool.ToolCallable:
    """生成预配置的单文件搜索工具（仅搜索可读文件）。"""
    working_directory = Path.cwd()
    tool_description = description or (
        "在指定文件中按正则表达式逐行搜索并输出（仅搜索可读文件）"
    )

    def search_file(
        pattern: str,
        path: str,
    ) -> str:
        try:
            regex = re.compile(pattern)
        except re.error as regex_error:
            raise ValueError(f"无效的正则表达式：{regex_error}") from regex_error
        resolved = egent.builtin_tools.path_validator.resolve_path(path)
        if not resolved.is_file():
            raise FileNotFoundError(f"文件不存在：{path}")
        return _search_file_content(resolved, regex, validator, path)

    search_file.__name__ = name
    search_file.__doc__ = (
        f"{tool_description}\n\n"
        "@param pattern 正则表达式\n"
        f"@param path 文件路径.如果填相对路径将以工作目录 {working_directory} 为基准"
    )
    return search_file


def get_read_file_tool(
    validator: egent.builtin_tools.path_validator.PathPermissions | None = None,
    name: str = "read_file",
    description: str | None = None,
) -> egent.tool.ToolCallable:
    """生成预配置的文件读取工具。"""
    working_directory = Path.cwd()
    tool_description = description or "读取指定文件内容"

    def read_file(
        path: str,
        line: int | None = None,
        column: int | None = None,
        limit: int | None = None,
    ) -> str:
        _, text = _read_utf8_file(
            path,
            validator,
            lambda path_validator, resolved_path: path_validator.is_readable(resolved_path),
        )
        file_lines = text.splitlines(keepends=True)
        start_line = line or 1
        start_column = column or 1
        content = _slice_lines_from_position(file_lines, start_line, start_column, limit)
        if not content:
            return "(空文件)"
        # 使用更低的截断阈值（egent.limits.TOOL_RESULT_MAX_CHARS * 9 // 10），且不保存临时文件。
        # 原因：文件本身在磁盘上，AI 可直接用 line/column 参数继续读取，无需额外副本。
        # 降低阈值可避免"读文件→截断→读临时文件→又被截断"的无意义循环。
        max_chars = egent.limits.TOOL_RESULT_MAX_CHARS * 9 // 10
        if len(content) <= max_chars:
            return content
        next_line, next_column = egent._line_position.position_after_characters(  # pylint: disable=protected-access
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

    read_file.__name__ = name
    read_file.__doc__ = (
        f"{tool_description}\n\n"
        f"@param path 文件路径,如果填相对路径将以工作目录 {working_directory} 为基准\n"
        "@param line 起始行号，从 1 开始，缺省 1\n"
        "@param column 起始列号，从 1 开始，缺省 1\n"
        "@param limit 读取行数，缺省读取到文件末尾"
    )
    return read_file


def get_create_file_tool(
    validator: egent.builtin_tools.path_validator.PathPermissions | None = None,
    name: str = "create_file",
    description: str | None = None,
) -> egent.tool.ToolCallable:
    """生成预配置的文件创建工具。"""
    working_directory = Path.cwd()
    tool_description = description or "创建新文件"

    def create_file(path: str, content: str) -> str:
        resolved_path = _resolve_scoped_path(path, validator)
        if resolved_path.is_file():
            raise FileExistsError(f"文件已存在：{path}")
        if not resolved_path.parent.is_dir():
            raise FileNotFoundError(f"父目录不存在：{path}")
        resolved_path.write_text(content, encoding="utf-8")
        return f"已创建文件：{resolved_path}"

    create_file.__name__ = name
    create_file.__doc__ = (
        f"{tool_description}\n\n"
        f"@param path 文件路径（如果填相对路径将以工作目录 {working_directory} 为基准）\n"
        "@param content 文件内容"
    )
    return create_file


def get_append_text_tool(
    validator: egent.builtin_tools.path_validator.PathPermissions | None = None,
    name: str = "append_text",
    description: str | None = None,
) -> egent.tool.ToolCallable:
    """生成预配置的文件追加写入工具。"""
    working_directory = Path.cwd()
    tool_description = description or "向文件追加文本"

    def append_text(path: str, text: str) -> str:
        resolved_path = _open_existing_file(path, validator)
        with resolved_path.open("a", encoding="utf-8") as file_handle:
            file_handle.write(text)
        return f"已追加写入：{resolved_path}"

    append_text.__name__ = name
    append_text.__doc__ = (
        f"{tool_description}\n\n"
        f"@param path 文件路径（如果填相对路径将以工作目录 {working_directory} 为基准）\n"
        "@param text 要追加的文本"
    )
    return append_text


def get_apply_patch_tool(
    validator: egent.builtin_tools.path_validator.PathPermissions | None = None,
    name: str = "apply_patch",
    description: str | None = None,
) -> egent.tool.ToolCallable:
    """生成预配置的文件补丁工具。"""
    working_directory = Path.cwd()
    tool_description = description or "按精确文本匹配替换文件内容，old_string 必须唯一匹配"

    def apply_patch(
        path: str,
        old_string: str,
        new_string: str,
    ) -> str:
        resolved_path, original_text = _read_utf8_file(
            path,
            validator,
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

    apply_patch.__name__ = name
    apply_patch.__doc__ = (
        f"{tool_description}\n\n"
        f"@param path 文件路径（如果填相对路径将以工作目录 {working_directory} 为基准）\n"
        "@param old_string 要被替换的原文本，需与文件内容完全一致且仅匹配一处\n"
        "@param new_string 替换后的文本"
    )
    return apply_patch


def get_replace_tool(
    validator: egent.builtin_tools.path_validator.PathPermissions | None = None,
    name: str = "replace",
    description: str | None = None,
) -> egent.tool.ToolCallable:
    """生成预配置的正则表达式全量替换工具。"""
    working_directory = Path.cwd()
    tool_description = description or "对文件内容执行正则表达式全量替换"

    def replace(path: str, pattern: str, replacement: str) -> str:
        resolved_path, original_text = _read_utf8_file(
            path,
            validator,
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

    replace.__name__ = name
    replace.__doc__ = (
        f"{tool_description}\n\n"
        f"@param path 文件路径（如果填相对路径将以工作目录 {working_directory} 为基准）\n"
        "@param pattern 正则表达式\n"
        "@param replacement 替换文本"
    )
    return replace


def get_rewrite_tool(
    validator: egent.builtin_tools.path_validator.PathPermissions | None = None,
    name: str = "rewrite",
    description: str | None = None,
) -> egent.tool.ToolCallable:
    """生成预配置的文件重写工具（覆盖或新建）。"""
    working_directory = Path.cwd()
    tool_description = description or "重新写入整个文件（覆盖已有或创建新文件）"

    def rewrite(path: str, content: str) -> str:
        resolved_path = _resolve_scoped_path(path, validator)
        if not resolved_path.parent.is_dir():
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_path.write_text(content, encoding="utf-8")
        return f"已写入文件：{resolved_path}"

    rewrite.__name__ = name
    rewrite.__doc__ = (
        f"{tool_description}\n\n"
        f"@param path 文件路径（如果填相对路径将以工作目录 {working_directory} 为基准）\n"
        "@param content 文件内容"
    )
    return rewrite


def get_delete_tool(
    validator: egent.builtin_tools.path_validator.PathPermissions | None = None,
    name: str = "delete",
    description: str | None = None,
) -> egent.tool.ToolCallable:
    """生成预配置的文件/目录删除工具。"""
    working_directory = Path.cwd()
    tool_description = description or "删除文件或目录（递归删除目录）"

    def delete(path: str) -> str:
        resolved_path = _resolve_scoped_path(path, validator)
        if not resolved_path.exists():
            raise FileNotFoundError(f"路径不存在：{path}")
        if resolved_path.is_file():
            resolved_path.unlink()
            return f"已删除文件：{resolved_path}"
        if resolved_path.is_dir():
            shutil.rmtree(resolved_path)
            return f"已删除目录：{resolved_path}"
        raise ValueError(f"路径不是文件也不是目录：{path}")

    delete.__name__ = name
    delete.__doc__ = (
        f"{tool_description}\n\n"
        f"@param path 文件或目录路径（如果填相对路径将以工作目录 {working_directory} 为基准）"
    )
    return delete


def get_list_path_permissions_tool(
    path_permissions: egent.builtin_tools.path_validator.PathPermissions,
    name: str = "list_path_permissions",
    description: str | None = None,
) -> egent.tool.ToolCallable:
    """生成预配置的路径权限列表工具。"""
    return egent.builtin_tools.path_validator.get_list_path_permissions_tool(
        path_permissions,
        name=name,
        description=description,
    )


def get_read_tools(
    path_permissions: egent.builtin_tools.path_validator.PathPermissions | None = None,
) -> tuple[
    egent.tool.ToolCallable,
    egent.tool.ToolCallable,
    egent.tool.ToolCallable,
    egent.tool.ToolCallable,
    egent.tool.ToolCallable,
]:
    """生成预配置的文件读取工具集（权限列表、遍历、读取、目录搜索、文件搜索）。"""
    list_tool = (
        get_list_path_permissions_tool(path_permissions)
        if path_permissions is not None
        else _get_unrestricted_path_permissions_list_tool()
    )
    return (
        list_tool,
        get_walk_files_tool(path_permissions),
        get_read_file_tool(path_permissions),
        get_search_directory_tool(path_permissions),
        get_search_file_tool(path_permissions),
    )


def _get_unrestricted_path_permissions_list_tool() -> egent.tool.ToolCallable:
    def list_path_permissions() -> str:
        return "路径权限未配置，所有路径均可访问。"

    list_path_permissions.__name__ = "list_path_permissions"
    list_path_permissions.__doc__ = "列出当前路径权限规则（可发现、可读、可编辑的白名单与黑名单）"
    return list_path_permissions


def get_edit_tools(
    path_permissions: egent.builtin_tools.path_validator.PathPermissions | None = None,
) -> tuple[
    egent.tool.ToolCallable,
    egent.tool.ToolCallable,
    egent.tool.ToolCallable,
    egent.tool.ToolCallable,
    egent.tool.ToolCallable,
    egent.tool.ToolCallable,
]:
    """生成预配置的文件编辑工具集（创建、追加、编辑、替换、重写、删除）。"""
    return (
        get_create_file_tool(path_permissions),
        get_append_text_tool(path_permissions),
        get_apply_patch_tool(path_permissions),
        get_replace_tool(path_permissions),
        get_rewrite_tool(path_permissions),
        get_delete_tool(path_permissions),
    )


def get_file_tools(
    path_permissions: egent.builtin_tools.path_validator.PathPermissions | None = None,
) -> tuple[egent.tool.ToolCallable, ...]:
    """生成预配置的全部文件系统内置工具。"""
    return get_read_tools(path_permissions) + get_edit_tools(path_permissions)


def get_tools(
    path_permissions: egent.builtin_tools.path_validator.PathPermissions | None = None,
) -> tuple[egent.tool.ToolCallable, ...]:
    """生成预配置的全部文件系统工具。"""
    return get_file_tools(path_permissions)
