"""PathValidator 单元测试。"""

from __future__ import annotations

from pathlib import Path
from typing import override

import egent.builtin_tools.path_validator


class _ReadableOnlyFileValidator(egent.builtin_tools.path_validator.PathValidator):
    def __init__(self, sample_file: Path) -> None:
        self._sample_file = sample_file

    @override
    def _is_discoverable(self, path: Path) -> bool:
        return path == self._sample_file

    @override
    def _is_readable(self, path: Path) -> bool:
        return False

    @override
    def _is_editable(self, path: Path) -> bool:
        return True

    @override
    def _is_searchable(self, path: Path) -> bool:
        return True


class _IgnoredFileValidator(egent.builtin_tools.path_validator.PathValidator):
    def __init__(self, sample_file: Path) -> None:
        self._sample_file = sample_file

    @override
    def _is_discoverable(self, path: Path) -> bool:
        return path != self._sample_file

    @override
    def _is_readable(self, path: Path) -> bool:
        return path != self._sample_file

    @override
    def _is_editable(self, path: Path) -> bool:
        return path != self._sample_file

    @override
    def _is_searchable(self, path: Path) -> bool:
        return path != self._sample_file


def test_is_searchable_requires_readable(tmp_path: Path) -> None:
    """is_searchable 应要求可读，但不要求可发现。"""
    sample_file = tmp_path / "sample.txt"
    sample_file.write_text("content", encoding="utf-8")
    path_validator = _ReadableOnlyFileValidator(sample_file)

    assert not path_validator.is_searchable(sample_file)


class _UndiscoverableButSearchableValidator(egent.builtin_tools.path_validator.PathValidator):
    def __init__(self, sample_file: Path) -> None:
        self._sample_file = sample_file

    @override
    def _is_discoverable(self, path: Path) -> bool:
        return False

    @override
    def _is_readable(self, path: Path) -> bool:
        return path == self._sample_file

    @override
    def _is_editable(self, path: Path) -> bool:
        return False

    @override
    def _is_searchable(self, path: Path) -> bool:
        return path == self._sample_file


def test_is_searchable_allows_undiscoverable_readable_path(tmp_path: Path) -> None:
    """is_searchable 应允许不可发现但可读的路径（如隐藏目录内文件）。"""
    sample_file = tmp_path / "sample.txt"
    sample_file.write_text("content", encoding="utf-8")
    path_validator = _UndiscoverableButSearchableValidator(sample_file)

    assert not path_validator.is_discoverable(sample_file)
    assert path_validator.is_searchable(sample_file)


def test_is_searchable_rejects_ignored_path(tmp_path: Path) -> None:
    """is_searchable 应拒绝被忽略的路径。"""
    sample_file = tmp_path / "sample.txt"
    path_validator = _IgnoredFileValidator(sample_file)

    assert not path_validator.is_searchable(sample_file)


def test_permission_methods_reject_ignored_before_custom_check(tmp_path: Path) -> None:
    """各权限方法应先排除被忽略的路径。"""
    sample_file = tmp_path / "sample.txt"
    path_validator = _IgnoredFileValidator(sample_file)

    assert not path_validator.is_discoverable(sample_file)
    assert not path_validator.is_readable(sample_file)
    assert not path_validator.is_editable(sample_file)
