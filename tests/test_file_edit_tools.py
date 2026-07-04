"""文件编辑内置工具单元测试。"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import override

import egent.builtin_tools.file_system_tools
import egent.builtin_tools.path_validator


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


class _UnderRootsValidator(egent.builtin_tools.path_validator.PathValidator):
    def __init__(self, *roots: Path) -> None:
        self._roots = tuple(root.resolve() for root in roots)

    def __under_roots(self, path: Path) -> bool:
        resolved_path = path.resolve()
        return any(resolved_path.is_relative_to(root) for root in self._roots)

    @override
    def _is_discoverable(self, path: Path) -> bool:
        return self.__under_roots(path)

    @override
    def _is_readable(self, path: Path) -> bool:
        return self.__under_roots(path)

    @override
    def _is_editable(self, path: Path) -> bool:
        return self.__under_roots(path)

    @override
    def _is_searchable(self, path: Path) -> bool:
        return self.__under_roots(path)


class _RejectPathPrefixValidator(_UnderRootValidator):
    def __init__(self, root: Path, pattern: str) -> None:
        super().__init__(root)
        self._pattern = pattern

    def __is_path_ignored(self, path: Path) -> bool:
        try:
            relative_text = path.resolve().relative_to(self._root).as_posix()
        except ValueError:
            return True
        return _matches_pattern(relative_text, self._pattern)

    @override
    def _is_discoverable(self, path: Path) -> bool:
        return not self.__is_path_ignored(path) and super()._is_discoverable(path)

    @override
    def _is_readable(self, path: Path) -> bool:
        return not self.__is_path_ignored(path) and super()._is_readable(path)

    @override
    def _is_editable(self, path: Path) -> bool:
        return not self.__is_path_ignored(path) and super()._is_editable(path)

    @override
    def _is_searchable(self, path: Path) -> bool:
        return not self.__is_path_ignored(path) and super()._is_searchable(path)


def _under_root(root: Path) -> egent.builtin_tools.path_validator.PathValidator:
    return _UnderRootValidator(root)


def _under_roots(*roots: Path) -> egent.builtin_tools.path_validator.PathValidator:
    return _UnderRootsValidator(*roots)


def _reject_path_prefix(root: Path, pattern: str) -> egent.builtin_tools.path_validator.PathValidator:
    return _RejectPathPrefixValidator(root, pattern)


def test_create_file_writes_content(tmp_path: Path) -> None:
    """create_file 应创建文件并写入内容。"""
    target_file = tmp_path / "notes.txt"
    create_file = egent.builtin_tools.file_system_tools.get_create_file_tool(_under_root(tmp_path))

    result = create_file(str(target_file), "hello")

    assert result == f"已创建文件：{target_file.resolve()}"
    assert target_file.read_text(encoding="utf-8") == "hello"


def test_create_file_accepts_relative_path(tmp_path: Path, monkeypatch) -> None:
    """create_file 应将相对路径以工作目录为基准解析。"""
    monkeypatch.chdir(tmp_path)
    create_file = egent.builtin_tools.file_system_tools.get_create_file_tool(_under_root(tmp_path))

    result = create_file("notes.txt", "hello")

    assert result == f"已创建文件：{(tmp_path / 'notes.txt').resolve()}"
    assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == "hello"


def test_create_file_rejects_existing_file(tmp_path: Path) -> None:
    """create_file 在文件已存在时应返回错误。"""
    sample_file = tmp_path / "notes.txt"
    sample_file.write_text("old", encoding="utf-8")
    create_file = egent.builtin_tools.file_system_tools.get_create_file_tool(_under_root(tmp_path))

    result = create_file(str(sample_file), "new")

    assert "文件已存在" in result
    assert sample_file.read_text(encoding="utf-8") == "old"


def test_create_file_respects_validator(tmp_path: Path) -> None:
    """create_file 应拒绝 validator 不允许的路径。"""
    target_file = tmp_path / "secret" / "hidden.txt"
    create_file = egent.builtin_tools.file_system_tools.get_create_file_tool(_reject_path_prefix(tmp_path, "secret/*"))

    result = create_file(str(target_file), "secret")

    assert "没有权限" in result
    assert not target_file.exists()


def test_create_file_supports_multiple_roots(tmp_path: Path) -> None:
    """create_file 应支持 validator 允许多个根目录。"""
    first_root = tmp_path / "project_a"
    second_root = tmp_path / "project_b"
    first_root.mkdir()
    second_root.mkdir()
    first_file = first_root / "notes.txt"
    second_file = second_root / "notes.txt"
    create_file = egent.builtin_tools.file_system_tools.get_create_file_tool(_under_roots(first_root, second_root))

    first_result = create_file(str(first_file), "a")
    second_result = create_file(str(second_file), "b")

    assert first_result == f"已创建文件：{first_file.resolve()}"
    assert second_result == f"已创建文件：{second_file.resolve()}"
    assert first_file.read_text(encoding="utf-8") == "a"
    assert second_file.read_text(encoding="utf-8") == "b"


def test_append_text_appends_content(tmp_path: Path) -> None:
    """append_text 应向现有文件追加文本。"""
    sample_file = tmp_path / "log.txt"
    sample_file.write_text("line1\n", encoding="utf-8")
    append_text = egent.builtin_tools.file_system_tools.get_append_text_tool(_under_root(tmp_path))

    result = append_text(str(sample_file), "line2\n")

    assert result == f"已追加写入：{sample_file.resolve()}"
    assert sample_file.read_text(encoding="utf-8") == "line1\nline2\n"


def test_append_text_missing_file(tmp_path: Path) -> None:
    """append_text 在文件不存在时应返回错误。"""
    append_text = egent.builtin_tools.file_system_tools.get_append_text_tool(_under_root(tmp_path))

    result = append_text(str(tmp_path / "missing.txt"), "text")

    assert "文件不存在" in result


def test_append_text_respects_validator(tmp_path: Path) -> None:
    """append_text 应拒绝修改 validator 不允许的路径。"""
    secret_directory = tmp_path / "secret"
    secret_directory.mkdir()
    sample_file = secret_directory / "hidden.txt"
    sample_file.write_text("keep", encoding="utf-8")
    append_text = egent.builtin_tools.file_system_tools.get_append_text_tool(_reject_path_prefix(tmp_path, "secret/*"))

    result = append_text(str(sample_file), "more")

    assert "没有权限" in result
    assert sample_file.read_text(encoding="utf-8") == "keep"


def test_apply_patch_replaces_single_match(tmp_path: Path) -> None:
    """apply_patch 应替换唯一匹配。"""
    sample_file = tmp_path / "alpha.txt"
    sample_file.write_text("foo bar foo", encoding="utf-8")
    apply_patch = egent.builtin_tools.file_system_tools.get_apply_patch_tool(_under_root(tmp_path))

    result = apply_patch(str(sample_file), "bar", "baz")

    assert result == f"已应用补丁：{sample_file.resolve()}"
    assert sample_file.read_text(encoding="utf-8") == "foo baz foo"


def test_apply_patch_rejects_ambiguous_match(tmp_path: Path) -> None:
    """apply_patch 在多处匹配时应返回错误。"""
    sample_file = tmp_path / "alpha.txt"
    sample_file.write_text("foo\nfoo\n", encoding="utf-8")
    apply_patch = egent.builtin_tools.file_system_tools.get_apply_patch_tool(_under_root(tmp_path))

    result = apply_patch(str(sample_file), "foo", "bar")

    assert "找到 2 处匹配" in result
    assert sample_file.read_text(encoding="utf-8") == "foo\nfoo\n"


def test_apply_patch_respects_validator(tmp_path: Path) -> None:
    """apply_patch 应拒绝修改 validator 不允许的路径。"""
    secret_directory = tmp_path / "secret"
    secret_directory.mkdir()
    sample_file = secret_directory / "hidden.txt"
    sample_file.write_text("secret", encoding="utf-8")
    apply_patch = egent.builtin_tools.file_system_tools.get_apply_patch_tool(_reject_path_prefix(tmp_path, "secret/*"))

    result = apply_patch(str(sample_file), "secret", "public")

    assert "没有权限" in result
    assert sample_file.read_text(encoding="utf-8") == "secret"


def test_edit_tools_share_validator(tmp_path: Path) -> None:
    """编辑工具应共用同一 validator 配置。"""
    notes_file = tmp_path / "notes.txt"
    path_validator = _reject_path_prefix(tmp_path, "secret/*")
    create_file = egent.builtin_tools.file_system_tools.get_create_file_tool(path_validator)
    append_text = egent.builtin_tools.file_system_tools.get_append_text_tool(path_validator)
    apply_patch = egent.builtin_tools.file_system_tools.get_apply_patch_tool(path_validator)
    replace = egent.builtin_tools.file_system_tools.get_replace_tool(path_validator)
    rewrite = egent.builtin_tools.file_system_tools.get_rewrite_tool(path_validator)
    delete = egent.builtin_tools.file_system_tools.get_delete_tool(path_validator)

    create_result = create_file(str(notes_file), "hello")
    append_result = append_text(str(notes_file), " world")
    patch_result = apply_patch(str(notes_file), "hello world", "hi world")

    assert create_result == f"已创建文件：{notes_file.resolve()}"
    assert append_result == f"已追加写入：{notes_file.resolve()}"
    assert patch_result == f"已应用补丁：{notes_file.resolve()}"
    assert notes_file.read_text(encoding="utf-8") == "hi world"

    # 验证新工具也共用同一 validator
    assert "没有权限" in create_file(str(tmp_path / "secret" / "hidden.txt"), "secret")

    # replace 工具也受 validator 限制
    assert "没有权限" in replace(str(tmp_path / "secret" / "hidden.txt"), "x", "y")

    # rewrite 工具也受 validator 限制
    assert "没有权限" in rewrite(str(tmp_path / "secret" / "hidden.txt"), "data")

    # delete 工具也受 validator 限制
    assert "没有权限" in delete(str(tmp_path / "secret" / "hidden.txt"))

# ==================== replace_tool 测试 ====================

def test_replace_single_match(tmp_path: Path) -> None:
    """replace 应替换单处匹配。"""
    sample_file = tmp_path / "text.txt"
    sample_file.write_text("hello world", encoding="utf-8")
    replace = egent.builtin_tools.file_system_tools.get_replace_tool(_under_root(tmp_path))

    result = replace(str(sample_file), r"world", "universe")

    assert result == f"已替换 1 处：{sample_file.resolve()}"
    assert sample_file.read_text(encoding="utf-8") == "hello universe"


def test_replace_multiple_matches(tmp_path: Path) -> None:
    """replace 应替换所有匹配。"""
    sample_file = tmp_path / "text.txt"
    sample_file.write_text("foo bar foo bar foo", encoding="utf-8")
    replace = egent.builtin_tools.file_system_tools.get_replace_tool(_under_root(tmp_path))

    result = replace(str(sample_file), r"foo", "baz")

    assert result == f"已替换 3 处：{sample_file.resolve()}"
    assert sample_file.read_text(encoding="utf-8") == "baz bar baz bar baz"


def test_replace_zero_matches(tmp_path: Path) -> None:
    """replace 在零匹配时应告知用户。"""
    sample_file = tmp_path / "text.txt"
    sample_file.write_text("hello world", encoding="utf-8")
    replace = egent.builtin_tools.file_system_tools.get_replace_tool(_under_root(tmp_path))

    result = replace(str(sample_file), r"xyz", "abc")

    assert "已替换 0 处" in result
    assert sample_file.read_text(encoding="utf-8") == "hello world"


def test_replace_invalid_regex(tmp_path: Path) -> None:
    """replace 在正则无效时应返回错误。"""
    sample_file = tmp_path / "text.txt"
    sample_file.write_text("hello", encoding="utf-8")
    replace = egent.builtin_tools.file_system_tools.get_replace_tool(_under_root(tmp_path))

    result = replace(str(sample_file), r"[invalid", "x")

    assert "无效的正则表达式" in result
    assert sample_file.read_text(encoding="utf-8") == "hello"


def test_replace_respects_validator(tmp_path: Path) -> None:
    """replace 应拒绝 validator 不允许的路径。"""
    secret_dir = tmp_path / "secret"
    secret_dir.mkdir()
    sample_file = secret_dir / "hidden.txt"
    sample_file.write_text("secret", encoding="utf-8")
    replace = egent.builtin_tools.file_system_tools.get_replace_tool(_reject_path_prefix(tmp_path, "secret/*"))

    result = replace(str(sample_file), r"secret", "public")

    assert "没有权限" in result
    assert sample_file.read_text(encoding="utf-8") == "secret"


def test_replace_missing_file(tmp_path: Path) -> None:
    """replace 在文件不存在时应返回错误。"""
    replace = egent.builtin_tools.file_system_tools.get_replace_tool(_under_root(tmp_path))

    result = replace(str(tmp_path / "missing.txt"), r"x", "y")

    assert "文件不存在" in result


def test_replace_relative_path(tmp_path: Path, monkeypatch) -> None:
    """replace 应将相对路径以工作目录为基准解析。"""
    monkeypatch.chdir(tmp_path)
    sample_file = tmp_path / "notes.txt"
    sample_file.write_text("alpha beta", encoding="utf-8")
    replace = egent.builtin_tools.file_system_tools.get_replace_tool(_under_root(tmp_path))

    result = replace("notes.txt", r"beta", "gamma")

    assert result == f"已替换 1 处：{sample_file.resolve()}"
    assert sample_file.read_text(encoding="utf-8") == "alpha gamma"


# ==================== rewrite_tool 测试 ====================

def test_rewrite_overwrite_existing(tmp_path: Path) -> None:
    """rewrite 应覆盖已存在文件。"""
    sample_file = tmp_path / "notes.txt"
    sample_file.write_text("old content", encoding="utf-8")
    rewrite = egent.builtin_tools.file_system_tools.get_rewrite_tool(_under_root(tmp_path))

    result = rewrite(str(sample_file), "new content")

    assert result == f"已写入文件：{sample_file.resolve()}"
    assert sample_file.read_text(encoding="utf-8") == "new content"


def test_rewrite_create_new_file(tmp_path: Path) -> None:
    """rewrite 应创建新文件。"""
    new_file = tmp_path / "new.txt"
    rewrite = egent.builtin_tools.file_system_tools.get_rewrite_tool(_under_root(tmp_path))

    result = rewrite(str(new_file), "fresh content")

    assert result == f"已写入文件：{new_file.resolve()}"
    assert new_file.read_text(encoding="utf-8") == "fresh content"


def test_rewrite_create_parent_directories(tmp_path: Path) -> None:
    """rewrite 应自动创建父目录。"""
    nested_file = tmp_path / "deep" / "nested" / "file.txt"
    rewrite = egent.builtin_tools.file_system_tools.get_rewrite_tool(_under_root(tmp_path))

    result = rewrite(str(nested_file), "deep content")

    assert result == f"已写入文件：{nested_file.resolve()}"
    assert nested_file.read_text(encoding="utf-8") == "deep content"


def test_rewrite_respects_validator(tmp_path: Path) -> None:
    """rewrite 应拒绝 validator 不允许的路径。"""
    rewrite = egent.builtin_tools.file_system_tools.get_rewrite_tool(_reject_path_prefix(tmp_path, "secret/*"))

    result = rewrite(str(tmp_path / "secret" / "hidden.txt"), "data")

    assert "没有权限" in result
    assert not (tmp_path / "secret").exists()


def test_rewrite_relative_path(tmp_path: Path, monkeypatch) -> None:
    """rewrite 应将相对路径以工作目录为基准解析。"""
    monkeypatch.chdir(tmp_path)
    rewrite = egent.builtin_tools.file_system_tools.get_rewrite_tool(_under_root(tmp_path))

    result = rewrite("notes.txt", "relative content")

    assert result == f"已写入文件：{(tmp_path / 'notes.txt').resolve()}"
    assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == "relative content"


# ==================== delete_tool 测试 ====================

def test_delete_file(tmp_path: Path) -> None:
    """delete 应删除文件。"""
    sample_file = tmp_path / "to_delete.txt"
    sample_file.write_text("content", encoding="utf-8")
    delete = egent.builtin_tools.file_system_tools.get_delete_tool(_under_root(tmp_path))

    result = delete(str(sample_file))

    assert result == f"已删除文件：{sample_file.resolve()}"
    assert not sample_file.exists()


def test_delete_directory(tmp_path: Path) -> None:
    """delete 应递归删除目录及其内容。"""
    test_dir = tmp_path / "to_delete_dir"
    test_dir.mkdir()
    (test_dir / "inner.txt").write_text("inner", encoding="utf-8")
    nested_dir = test_dir / "nested"
    nested_dir.mkdir()
    (nested_dir / "deep.txt").write_text("deep", encoding="utf-8")
    delete = egent.builtin_tools.file_system_tools.get_delete_tool(_under_root(tmp_path))

    result = delete(str(test_dir))

    assert result == f"已删除目录：{test_dir.resolve()}"
    assert not test_dir.exists()


def test_delete_nonexistent_path(tmp_path: Path) -> None:
    """delete 在路径不存在时应返回错误。"""
    delete = egent.builtin_tools.file_system_tools.get_delete_tool(_under_root(tmp_path))

    result = delete(str(tmp_path / "nonexistent"))

    assert "路径不存在" in result


def test_delete_respects_validator(tmp_path: Path) -> None:
    """delete 应拒绝 validator 不允许的路径。"""
    secret_dir = tmp_path / "secret"
    secret_dir.mkdir()
    sample_file = secret_dir / "hidden.txt"
    sample_file.write_text("secret", encoding="utf-8")
    delete = egent.builtin_tools.file_system_tools.get_delete_tool(_reject_path_prefix(tmp_path, "secret/*"))

    result = delete(str(sample_file))

    assert "没有权限" in result
    assert sample_file.exists()
