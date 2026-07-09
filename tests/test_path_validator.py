"""PathPermissions 单元测试。"""

from __future__ import annotations

from pathlib import Path

import egent.builtin_tools.path_validator


def _scope_pattern(scope: Path, pattern: str) -> str:
    if egent.builtin_tools.path_validator.is_absolute_path_pattern(pattern):
        return pattern
    scope_posix = scope.resolve().as_posix()
    return f"{scope_posix}/{pattern}"


def _scope_patterns(scope: Path, patterns: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_scope_pattern(scope, pattern) for pattern in patterns)


def _permissions(
    scope: Path,
    **overrides: tuple[str, ...],
) -> egent.builtin_tools.path_validator.PathPermissions:
    defaults = {
        "discoverable_whitelist": ("**",),
        "discoverable_blacklist": (),
        "readable_whitelist": ("**",),
        "readable_blacklist": (),
        "editable_whitelist": ("**",),
        "editable_blacklist": (),
    }
    values = {**defaults, **overrides}
    return egent.builtin_tools.path_validator.PathPermissions(
        discoverable=egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=_scope_patterns(scope, values["discoverable_whitelist"]),
            blacklist=_scope_patterns(scope, values["discoverable_blacklist"]),
        ),
        readable=egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=_scope_patterns(scope, values["readable_whitelist"]),
            blacklist=_scope_patterns(scope, values["readable_blacklist"]),
        ),
        editable=egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=_scope_patterns(scope, values["editable_whitelist"]),
            blacklist=_scope_patterns(scope, values["editable_blacklist"]),
        ),
    )


def test_allows_requires_whitelist_match(tmp_path: Path) -> None:
    """未匹配白名单的路径应被拒绝。"""
    sample_file = tmp_path / "sample.txt"
    sample_file.write_text("content", encoding="utf-8")
    permissions = _permissions(
        tmp_path,
        readable_whitelist=("other/**",),
    )

    assert not permissions.is_readable(sample_file)


def test_allows_rejects_blacklist_match(tmp_path: Path) -> None:
    """匹配黑名单的路径应被拒绝。"""
    sample_file = tmp_path / "sample.txt"
    sample_file.write_text("content", encoding="utf-8")
    permissions = _permissions(
        tmp_path,
        readable_blacklist=("sample.txt",),
    )

    assert not permissions.is_readable(sample_file)


def test_is_searchable_requires_discoverable_and_readable(tmp_path: Path) -> None:
    """is_searchable 应要求可发现且可读。"""
    sample_file = tmp_path / "sample.txt"
    sample_file.write_text("content", encoding="utf-8")
    permissions = _permissions(
        tmp_path,
        discoverable_whitelist=("sample.txt",),
        readable_whitelist=("other/**",),
    )

    assert permissions.is_discoverable(sample_file)
    assert not permissions.is_readable(sample_file)
    assert not permissions.is_searchable(sample_file)


def test_is_searchable_requires_both_permissions(tmp_path: Path) -> None:
    """可读但不可发现的路径不应可搜索。"""
    sample_file = tmp_path / "hidden" / "sample.txt"
    sample_file.parent.mkdir()
    sample_file.write_text("content", encoding="utf-8")
    permissions = _permissions(
        tmp_path,
        discoverable_blacklist=("hidden/**",),
    )

    assert not permissions.is_discoverable(sample_file)
    assert permissions.is_readable(sample_file)
    assert not permissions.is_searchable(sample_file)


def test_outside_whitelist_has_no_permissions(tmp_path: Path) -> None:
    """未命中白名单的路径应无任何权限。"""
    scope_directory = tmp_path / "scope"
    scope_directory.mkdir()
    outside_directory = tmp_path / "outside"
    outside_directory.mkdir()
    outside_file = outside_directory / "sample.txt"
    outside_file.write_text("content", encoding="utf-8")
    permissions = _permissions(scope_directory)

    assert not permissions.is_discoverable(outside_file)
    assert not permissions.is_readable(outside_file)
    assert not permissions.is_editable(outside_file)
    assert not permissions.is_searchable(outside_file)


def test_absolute_patterns_allow_multiple_directories(tmp_path: Path) -> None:
    """绝对路径白名单应支持多个互不相关的目录。"""
    first_directory = tmp_path / "project_a"
    second_directory = tmp_path / "project_b"
    first_directory.mkdir()
    second_directory.mkdir()
    first_file = first_directory / "one.txt"
    second_file = second_directory / "two.txt"
    first_file.write_text("one", encoding="utf-8")
    second_file.write_text("two", encoding="utf-8")
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("outside", encoding="utf-8")
    permissions = egent.builtin_tools.path_validator.PathPermissions(
        discoverable=egent.builtin_tools.path_validator.PathPermissionRule(whitelist=()),
        readable=egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=(
                f"{first_directory.resolve().as_posix()}/**",
                f"{second_directory.resolve().as_posix()}/**",
            ),
        ),
        editable=egent.builtin_tools.path_validator.PathPermissionRule(whitelist=()),
    )

    assert permissions.is_readable(first_file)
    assert permissions.is_readable(second_file)
    assert not permissions.is_readable(outside_file)


def test_relative_patterns_match_cwd(tmp_path: Path, monkeypatch) -> None:
    """相对路径白名单应匹配相对当前工作目录的路径。"""
    monkeypatch.chdir(tmp_path)
    sample_file = tmp_path / "sample.txt"
    sample_file.write_text("content", encoding="utf-8")
    permissions = egent.builtin_tools.path_validator.PathPermissions(
        discoverable=egent.builtin_tools.path_validator.PathPermissionRule(whitelist=()),
        readable=egent.builtin_tools.path_validator.PathPermissionRule(whitelist=("**",)),
        editable=egent.builtin_tools.path_validator.PathPermissionRule(whitelist=()),
    )

    assert permissions.is_readable(sample_file)


def test_format_rules_includes_all_permissions(tmp_path: Path) -> None:
    """format_rules 应输出三项权限的白名单与黑名单。"""
    permissions = _permissions(
        tmp_path,
        readable_blacklist=("secret/**",),
    )

    formatted = permissions.format_rules()

    assert "可发现:" in formatted
    assert "可读:" in formatted
    assert "可编辑:" in formatted
    assert "secret/**" in formatted
    assert "目录搜索: 可发现且可读" in formatted
    assert "文件搜索: 可读" in formatted


def test_list_path_permissions_tool_returns_formatted_rules(tmp_path: Path) -> None:
    """list_path_permissions 工具应返回格式化后的权限规则。"""
    permissions = _permissions(tmp_path)
    list_tool = egent.builtin_tools.path_validator.get_list_path_permissions_tool(permissions)

    result = list_tool()

    assert permissions.format_rules() == result
