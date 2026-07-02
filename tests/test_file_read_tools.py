"""文件读取内置工具单元测试。"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import override

import egent.builtin_tools.file_system_tools
import egent.builtin_tools.path_validator
import egent.limits


def _matches_pattern(relative_text: str, pattern: str) -> bool:
    path_segments = PurePosixPath(relative_text).parts
    for segment_count in range(1, len(path_segments) + 1):
        path_prefix = PurePosixPath(*path_segments[:segment_count])
        if path_prefix.full_match(pattern):
            return True
    return False


class _UnderRootValidator(egent.builtin_tools.path_validator.PathValidator):
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    @override
    def _is_discoverable(self, path: Path) -> bool:
        return path.resolve().is_relative_to(self._root)

    @override
    def _is_readable(self, path: Path) -> bool:
        return path.resolve().is_relative_to(self._root)

    @override
    def _is_editable(self, path: Path) -> bool:
        return path.resolve().is_relative_to(self._root)

    @override
    def _is_searchable(self, path: Path) -> bool:
        return path.resolve().is_relative_to(self._root)


class _RejectPathPrefixValidator(_UnderRootValidator):
    def __init__(self, root: Path, pattern: str) -> None:
        super().__init__(root)
        self._pattern = pattern

    def _is_path_ignored(self, path: Path) -> bool:
        try:
            relative_text = path.resolve().relative_to(self._root).as_posix()
        except ValueError:
            return True
        return _matches_pattern(relative_text, self._pattern)

    @override
    def _is_discoverable(self, path: Path) -> bool:
        return not self._is_path_ignored(path) and super()._is_discoverable(path)

    @override
    def _is_readable(self, path: Path) -> bool:
        return not self._is_path_ignored(path) and super()._is_readable(path)

    @override
    def _is_editable(self, path: Path) -> bool:
        return not self._is_path_ignored(path) and super()._is_editable(path)

    @override
    def _is_searchable(self, path: Path) -> bool:
        return not self._is_path_ignored(path) and super()._is_searchable(path)


def _under_root(root: Path) -> egent.builtin_tools.path_validator.PathValidator:
    return _UnderRootValidator(root)


def _reject_path_prefix(root: Path, pattern: str) -> egent.builtin_tools.path_validator.PathValidator:
    return _RejectPathPrefixValidator(root, pattern)


def test_read_file_returns_content(tmp_path: Path, monkeypatch) -> None:
    """read_file 应返回完整文件内容。"""
    monkeypatch.chdir(tmp_path)
    sample_file = tmp_path / "hello.txt"
    sample_file.write_text("line1\nline2\nline3\n", encoding="utf-8")
    read_file = egent.builtin_tools.file_system_tools.get_read_file_tool(_under_root(tmp_path))

    result = read_file("hello.txt")

    assert result == "line1\nline2\nline3\n"


def test_read_file_with_line_and_limit(tmp_path: Path, monkeypatch) -> None:
    """read_file 应按 line 与 limit 截取行。"""
    monkeypatch.chdir(tmp_path)
    sample_file = tmp_path / "lines.txt"
    sample_file.write_text("a\nb\nc\nd\n", encoding="utf-8")
    read_file = egent.builtin_tools.file_system_tools.get_read_file_tool(_under_root(tmp_path))

    result = read_file("lines.txt", line=2, limit=2)

    assert result == "b\nc\n"


def test_read_file_with_column(tmp_path: Path, monkeypatch) -> None:
    """read_file 应按 column 从行内指定位置开始读取。"""
    monkeypatch.chdir(tmp_path)
    sample_file = tmp_path / "partial.txt"
    sample_file.write_text("abcdef\n", encoding="utf-8")
    read_file = egent.builtin_tools.file_system_tools.get_read_file_tool(_under_root(tmp_path))

    result = read_file("partial.txt", line=1, column=3)

    assert result == "cdef\n"


def test_read_file_missing(tmp_path: Path, monkeypatch) -> None:
    """read_file 在文件不存在时应返回错误信息。"""
    monkeypatch.chdir(tmp_path)
    read_file = egent.builtin_tools.file_system_tools.get_read_file_tool(_under_root(tmp_path))

    result = read_file("missing.txt")

    assert "文件不存在" in result


def test_read_file_truncates_long_content(tmp_path: Path, monkeypatch) -> None:
    """read_file 应截断超出上限的内容。"""
    monkeypatch.chdir(tmp_path)
    sample_file = tmp_path / "large.txt"
    sample_file.write_text("x" * (egent.limits.TOOL_RESULT_MAX_CHARS + 100), encoding="utf-8")
    read_file = egent.builtin_tools.file_system_tools.get_read_file_tool(_under_root(tmp_path))

    result = read_file("large.txt")

    assert "内容太长被截断" in result
    assert len(result) < len("x" * (egent.limits.TOOL_RESULT_MAX_CHARS + 100))


def test_read_file_truncation_reports_continuation_position(tmp_path: Path, monkeypatch) -> None:
    """read_file 截断时应提示续读的 line 与 column。"""
    monkeypatch.chdir(tmp_path)
    max_chars = egent.limits.TOOL_RESULT_MAX_CHARS * 9 // 10
    sample_file = tmp_path / "large.txt"
    sample_file.write_text("x" * (max_chars + 50), encoding="utf-8")
    read_file = egent.builtin_tools.file_system_tools.get_read_file_tool(_under_root(tmp_path))

    first_result = read_file("large.txt")
    continuation = read_file("large.txt", line=1, column=max_chars + 1)

    assert f"line=1 column={max_chars + 1}" in first_result
    assert continuation == "x" * 50


def test_walk_files_lists_entries(tmp_path: Path, monkeypatch) -> None:
    """walk_files 应列出目录中的可见文件。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alpha.txt").write_text("a", encoding="utf-8")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "beta.txt").write_text("b", encoding="utf-8")

    walk_files = egent.builtin_tools.file_system_tools.get_walk_files_tool(_under_root(tmp_path))
    result = walk_files(".")

    assert "alpha.txt" in result
    assert "subdir/" in result


def test_walk_files_directories_first(tmp_path: Path, monkeypatch) -> None:
    """walk_files 应将文件夹排在文件前面。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "z_file.txt").write_text("z", encoding="utf-8")
    (tmp_path / "m_dir").mkdir()
    (tmp_path / "a_file.txt").write_text("a", encoding="utf-8")
    (tmp_path / "z_dir").mkdir()

    walk_files = egent.builtin_tools.file_system_tools.get_walk_files_tool(_under_root(tmp_path))
    result = walk_files(".")

    m_dir_index = result.index("m_dir/")
    z_dir_index = result.index("z_dir/")
    a_file_index = result.index("a_file.txt")
    z_file_index = result.index("z_file.txt")

    assert m_dir_index < z_dir_index
    assert z_dir_index < a_file_index
    assert a_file_index < z_file_index


def test_walk_files_respects_validator(tmp_path: Path, monkeypatch) -> None:
    """walk_files 应跳过 validator 拒绝的路径。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "public.txt").write_text("a", encoding="utf-8")
    secret_directory = tmp_path / "secret"
    secret_directory.mkdir()
    (secret_directory / "hidden.txt").write_text("b", encoding="utf-8")

    walk_files = egent.builtin_tools.file_system_tools.get_walk_files_tool(_reject_path_prefix(tmp_path, "secret"))
    result = walk_files(".")

    assert "public.txt" in result
    assert "secret" not in result


def test_walk_files_hides_git_with_glob_pattern(tmp_path: Path, monkeypatch) -> None:
    """walk_files 应通过 validator 屏蔽 .git 目录。"""
    monkeypatch.chdir(tmp_path)
    git_directory = tmp_path / ".git"
    git_directory.mkdir()
    (git_directory / "HEAD").write_text("ref", encoding="utf-8")
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")

    walk_files = egent.builtin_tools.file_system_tools.get_walk_files_tool(_reject_path_prefix(tmp_path, "**/.git"))
    result = walk_files(".", depth=0)

    assert "README.md" in result
    assert ".git" not in result


def test_read_file_respects_validator(tmp_path: Path, monkeypatch) -> None:
    """read_file 应拒绝 validator 不允许的路径。"""
    monkeypatch.chdir(tmp_path)
    secret_directory = tmp_path / "secret"
    secret_directory.mkdir()
    secret_file = secret_directory / "hidden.txt"
    secret_file.write_text("secret", encoding="utf-8")
    read_file_tool = egent.builtin_tools.file_system_tools.get_read_file_tool(_reject_path_prefix(tmp_path, "secret/*"))

    result = read_file_tool("secret/hidden.txt")

    assert "没有权限" in result


def test_search_matches_line_content(tmp_path: Path, monkeypatch) -> None:
    """search 应匹配文件行内容。"""
    monkeypatch.chdir(tmp_path)
    sample_file = tmp_path / "alpha.txt"
    sample_file.write_text("hello\nworld\nhello again\n", encoding="utf-8")

    search = egent.builtin_tools.file_system_tools.get_search_tool(_under_root(tmp_path))
    result = search("hello")

    assert result == "[alpha.txt line1] hello\n[alpha.txt line3] hello again"


def test_search_matches_filename(tmp_path: Path, monkeypatch) -> None:
    """search 应匹配文件名。"""
    monkeypatch.chdir(tmp_path)
    target_file = tmp_path / "needle.txt"
    target_file.write_text("plain text\n", encoding="utf-8")
    (tmp_path / "other.txt").write_text("plain text\n", encoding="utf-8")

    search = egent.builtin_tools.file_system_tools.get_search_tool(_under_root(tmp_path))
    result = search("needle")

    assert result == "[needle.txt]"


def test_search_respects_validator(tmp_path: Path, monkeypatch) -> None:
    """search 应忽略 validator 拒绝的文件。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "public.txt").write_text("secret word\n", encoding="utf-8")
    secret_directory = tmp_path / "secret"
    secret_directory.mkdir()
    (secret_directory / "hidden.txt").write_text("secret word\n", encoding="utf-8")

    search = egent.builtin_tools.file_system_tools.get_search_tool(_reject_path_prefix(tmp_path, "secret/*"))
    result = search("secret")

    assert "[public.txt line1] secret word" in result
    assert "hidden.txt" not in result


def test_search_invalid_regex(tmp_path: Path, monkeypatch) -> None:
    """search 在正则无效时应返回错误信息。"""
    monkeypatch.chdir(tmp_path)
    search = egent.builtin_tools.file_system_tools.get_search_tool(_under_root(tmp_path))

    result = search("(")

    assert "无效的正则表达式" in result


def test_search_file_mode_single_file(tmp_path: Path, monkeypatch) -> None:
    """search 在 directory 为文件路径时应在单文件中逐行搜索。"""
    monkeypatch.chdir(tmp_path)
    sample_file = tmp_path / "data.log"
    sample_file.write_text("error: timeout\ninfo: ok\nerror: retry\n", encoding="utf-8")

    search = egent.builtin_tools.file_system_tools.get_search_tool(_under_root(tmp_path))
    result = search("error", directory="data.log")

    assert result == "[data.log line1] error: timeout\n[data.log line3] error: retry"


def test_search_file_mode_no_match(tmp_path: Path, monkeypatch) -> None:
    """search 文件模式下无匹配应返回 (无匹配)。"""
    monkeypatch.chdir(tmp_path)
    sample_file = tmp_path / "notes.txt"
    sample_file.write_text("hello world\n", encoding="utf-8")

    search = egent.builtin_tools.file_system_tools.get_search_tool(_under_root(tmp_path))
    result = search("NOTFOUND", directory="notes.txt")

    assert result == "(无匹配)"


def test_search_file_mode_respects_validator(tmp_path: Path, monkeypatch) -> None:
    """search 文件模式下应校验 validator.is_searchable。"""
    monkeypatch.chdir(tmp_path)
    secret_dir = tmp_path / "secret"
    secret_dir.mkdir()
    secret_file = secret_dir / "private.txt"
    secret_file.write_text("classified data\n", encoding="utf-8")

    search = egent.builtin_tools.file_system_tools.get_search_tool(_reject_path_prefix(tmp_path, "secret/*"))
    result = search("classified", directory="secret/private.txt")

    assert "没有权限" in result


def test_search_filter_glob_in_directory(tmp_path: Path, monkeypatch) -> None:
    """search filter 参数应对目录下的文件名做 glob 过滤。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.py").write_text("import os\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("import os\n", encoding="utf-8")
    (tmp_path / "c.py").write_text("print('hi')\n", encoding="utf-8")

    search = egent.builtin_tools.file_system_tools.get_search_tool(_under_root(tmp_path))
    result = search("import", file_filter="*.py")

    assert "[a.py line1] import os" in result
    assert "b.txt" not in result
    assert "c.py" not in result


def test_search_filter_ignored_in_file_mode(tmp_path: Path, monkeypatch) -> None:
    """search filter 在文件模式下应被忽略。"""
    monkeypatch.chdir(tmp_path)
    sample_file = tmp_path / "data.py"
    sample_file.write_text("import sys\n", encoding="utf-8")

    search = egent.builtin_tools.file_system_tools.get_search_tool(_under_root(tmp_path))
    result = search("import", directory="data.py", file_filter="*.txt")

    assert "[data.py line1] import sys" in result
