"""文件读取内置工具单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

import egent.builtin_tools.file_system_tools
import egent.builtin_tools.path_validator
import egent.limits


def _under_root(_root: Path) -> egent.builtin_tools.path_validator.PathPermissions:
    allow_all = egent.builtin_tools.path_validator.PathPermissionRule(whitelist=("*",))
    return egent.builtin_tools.path_validator.PathPermissions(
        discoverable=allow_all,
        readable=allow_all,
        editable=allow_all,
    )


def _reject_path_prefix(
    root: Path,
    pattern: str,
) -> egent.builtin_tools.path_validator.PathPermissions:
    base = _under_root(root)
    if egent.builtin_tools.path_validator.is_absolute_path_pattern(pattern):
        scoped_pattern = pattern
    elif pattern.startswith("*/"):
        scoped_pattern = pattern
    else:
        scoped_pattern = f"{root.resolve().as_posix()}/{pattern}"

    def with_blacklist(
        rule: egent.builtin_tools.path_validator.PathPermissionRule,
    ) -> egent.builtin_tools.path_validator.PathPermissionRule:
        return egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=rule.whitelist,
            blacklist=rule.blacklist + (scoped_pattern,),
        )

    return egent.builtin_tools.path_validator.PathPermissions(
        discoverable=with_blacklist(base.discoverable),
        readable=with_blacklist(base.readable),
        editable=with_blacklist(base.editable),
    )


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
    """read_file 在文件不存在时应抛出异常。"""
    monkeypatch.chdir(tmp_path)
    read_file = egent.builtin_tools.file_system_tools.get_read_file_tool(_under_root(tmp_path))

    with pytest.raises(FileNotFoundError, match="文件不存在"):
        read_file("missing.txt")


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

    walk_files = egent.builtin_tools.file_system_tools.get_walk_files_tool(_reject_path_prefix(tmp_path, "*/.git"))
    result = walk_files(".", depth=0)

    assert "README.md" in result
    assert ".git" not in result


def _reject_discoverable_only(
    root: Path,
    pattern: str,
) -> egent.builtin_tools.path_validator.PathPermissions:
    base = _under_root(root)
    if egent.builtin_tools.path_validator.is_absolute_path_pattern(pattern):
        scoped_pattern = pattern
    else:
        scoped_pattern = f"{root.resolve().as_posix()}/{pattern}"

    def with_blacklist(
        rule: egent.builtin_tools.path_validator.PathPermissionRule,
    ) -> egent.builtin_tools.path_validator.PathPermissionRule:
        return egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=rule.whitelist,
            blacklist=rule.blacklist + (scoped_pattern,),
        )

    return egent.builtin_tools.path_validator.PathPermissions(
        discoverable=with_blacklist(base.discoverable),
        readable=base.readable,
        editable=base.editable,
    )

def test_read_file_respects_validator(tmp_path: Path, monkeypatch) -> None:
    """read_file 应拒绝 validator 不允许的路径。"""
    monkeypatch.chdir(tmp_path)
    secret_directory = tmp_path / "secret"
    secret_directory.mkdir()
    secret_file = secret_directory / "hidden.txt"
    secret_file.write_text("secret", encoding="utf-8")
    read_file_tool = egent.builtin_tools.file_system_tools.get_read_file_tool(_reject_path_prefix(tmp_path, "secret/*"))

    with pytest.raises(PermissionError, match="没有权限"):
        read_file_tool("secret/hidden.txt")


def test_search_directory_matches_line_content(tmp_path: Path, monkeypatch) -> None:
    """search_directory 应匹配文件行内容。"""
    monkeypatch.chdir(tmp_path)
    sample_file = tmp_path / "alpha.txt"
    sample_file.write_text("hello\nworld\nhello again\n", encoding="utf-8")

    search_directory = egent.builtin_tools.file_system_tools.get_search_directory_tool(_under_root(tmp_path))
    result = search_directory("hello")

    assert result == "[alpha.txt line1] hello\n[alpha.txt line3] hello again"


def test_search_directory_matches_filename(tmp_path: Path, monkeypatch) -> None:
    """search_directory 应匹配文件名。"""
    monkeypatch.chdir(tmp_path)
    target_file = tmp_path / "needle.txt"
    target_file.write_text("plain text\n", encoding="utf-8")
    (tmp_path / "other.txt").write_text("plain text\n", encoding="utf-8")

    search_directory = egent.builtin_tools.file_system_tools.get_search_directory_tool(_under_root(tmp_path))
    result = search_directory("needle")

    assert result == "[needle.txt]"


def test_search_directory_respects_validator(tmp_path: Path, monkeypatch) -> None:
    """search_directory 应忽略不可发现或不可读的文件。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "public.txt").write_text("secret word\n", encoding="utf-8")
    secret_directory = tmp_path / "secret"
    secret_directory.mkdir()
    (secret_directory / "hidden.txt").write_text("secret word\n", encoding="utf-8")

    search_directory = egent.builtin_tools.file_system_tools.get_search_directory_tool(
        _reject_path_prefix(tmp_path, "secret/*"),
    )
    result = search_directory("secret")

    assert "[public.txt line1] secret word" in result
    assert "hidden.txt" not in result


def test_search_directory_invalid_regex(tmp_path: Path, monkeypatch) -> None:
    """search_directory 在正则无效时应抛出异常。"""
    monkeypatch.chdir(tmp_path)
    search_directory = egent.builtin_tools.file_system_tools.get_search_directory_tool(_under_root(tmp_path))

    with pytest.raises(ValueError, match="无效的正则表达式"):
        search_directory("(")


def test_search_file_matches_line_content(tmp_path: Path, monkeypatch) -> None:
    """search_file 应在单文件中逐行搜索。"""
    monkeypatch.chdir(tmp_path)
    sample_file = tmp_path / "data.log"
    sample_file.write_text("error: timeout\ninfo: ok\nerror: retry\n", encoding="utf-8")

    search_file = egent.builtin_tools.file_system_tools.get_search_file_tool(_under_root(tmp_path))
    result = search_file("error", path="data.log")

    assert result == "[data.log line1] error: timeout\n[data.log line3] error: retry"


def test_search_file_no_match(tmp_path: Path, monkeypatch) -> None:
    """search_file 无匹配应返回 (无匹配)。"""
    monkeypatch.chdir(tmp_path)
    sample_file = tmp_path / "notes.txt"
    sample_file.write_text("hello world\n", encoding="utf-8")

    search_file = egent.builtin_tools.file_system_tools.get_search_file_tool(_under_root(tmp_path))
    result = search_file("NOTFOUND", path="notes.txt")

    assert result == "(无匹配)"


def test_search_file_respects_readable_permission(tmp_path: Path, monkeypatch) -> None:
    """search_file 应校验 is_readable。"""
    monkeypatch.chdir(tmp_path)
    secret_dir = tmp_path / "secret"
    secret_dir.mkdir()
    secret_file = secret_dir / "private.txt"
    secret_file.write_text("classified data\n", encoding="utf-8")

    search_file = egent.builtin_tools.file_system_tools.get_search_file_tool(
        _reject_path_prefix(tmp_path, "secret/*"),
    )
    with pytest.raises(PermissionError, match="没有权限"):
        search_file("classified", path="secret/private.txt")


def test_search_file_allows_readable_but_not_discoverable(tmp_path: Path, monkeypatch) -> None:
    """search_file 应允许搜索可读但不可发现的文件。"""
    monkeypatch.chdir(tmp_path)
    secret_dir = tmp_path / "secret"
    secret_dir.mkdir()
    secret_file = secret_dir / "private.txt"
    secret_file.write_text("classified data\n", encoding="utf-8")

    search_file = egent.builtin_tools.file_system_tools.get_search_file_tool(
        _reject_discoverable_only(tmp_path, "secret/*"),
    )
    result = search_file("classified", path="secret/private.txt")

    assert result == "[private.txt line1] classified data"


def test_search_directory_skips_not_discoverable(tmp_path: Path, monkeypatch) -> None:
    """search_directory 应跳过不可发现但可读的文件。"""
    monkeypatch.chdir(tmp_path)
    secret_dir = tmp_path / "secret"
    secret_dir.mkdir()
    (secret_dir / "private.txt").write_text("classified data\n", encoding="utf-8")

    search_directory = egent.builtin_tools.file_system_tools.get_search_directory_tool(
        _reject_discoverable_only(tmp_path, "secret/*"),
    )
    result = search_directory("classified")

    assert result == "(无匹配)"


def test_search_directory_filter_glob(tmp_path: Path, monkeypatch) -> None:
    """search_directory 的 file_filter 应对文件名做 glob 过滤。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.py").write_text("import os\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("import os\n", encoding="utf-8")
    (tmp_path / "c.py").write_text("print('hi')\n", encoding="utf-8")

    search_directory = egent.builtin_tools.file_system_tools.get_search_directory_tool(_under_root(tmp_path))
    result = search_directory("import", file_filter="*.py")

    assert "[a.py line1] import os" in result
    assert "b.txt" not in result
    assert "c.py" not in result


def test_search_file_stops_at_max_lines(tmp_path: Path, monkeypatch) -> None:
    """search_file 应在达到上限时停止继续匹配。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(egent.limits, "SEARCH_RESULT_MAX_LINES", 3)
    sample_file = tmp_path / "many.txt"
    sample_file.write_text("hit\n" * 10, encoding="utf-8")

    search_file = egent.builtin_tools.file_system_tools.get_search_file_tool(_under_root(tmp_path))
    result = search_file("hit", path="many.txt")
    result_lines = result.splitlines()

    assert result_lines[:3] == [
        "[many.txt line1] hit",
        "[many.txt line2] hit",
        "[many.txt line3] hit",
    ]
    assert result_lines[-1] == "(匹配过多已截断)"
    assert "line4" not in result


def test_search_directory_stops_at_max_lines(tmp_path: Path, monkeypatch) -> None:
    """search_directory 应在达到上限时停止继续扫描后续文件。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(egent.limits, "SEARCH_RESULT_MAX_LINES", 2)
    (tmp_path / "a.txt").write_text("hit\nhit\nhit\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("hit\n", encoding="utf-8")

    search_directory = egent.builtin_tools.file_system_tools.get_search_directory_tool(_under_root(tmp_path))
    result = search_directory("hit")
    result_lines = result.splitlines()

    assert result_lines[:2] == [
        "[a.txt line1] hit",
        "[a.txt line2] hit",
    ]
    assert result_lines[-1] == "(匹配过多已截断)"
    assert "a.txt line3" not in result
    assert "b.txt" not in result
