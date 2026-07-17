"""``.egent`` 临时目录容量维护单元测试。"""

from __future__ import annotations

import os
import time
from pathlib import Path

import egent.ephemeral_dirs


def _touch_dir(path: Path, modified_timestamp: float) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / ".keep").write_text("", encoding="utf-8")
    os.utime(path, (modified_timestamp, modified_timestamp))
    os.utime(path / ".keep", (modified_timestamp, modified_timestamp))


def test_prune_stale_subdirs_removes_old_subdirs(tmp_path: Path) -> None:
    """超出期限的子目录应被删除。"""
    root = tmp_path / "ephemeral"
    root.mkdir()
    project = root / "my-project"
    project.mkdir()
    _touch_dir(project / "old-session", time.time() - 20 * 86400)
    _touch_dir(project / "fresh-session", time.time() - 100)

    egent.ephemeral_dirs.prune_stale_subdirs(root, max_age_days=10)

    remaining = sorted(p.name for p in project.iterdir())
    assert remaining == ["fresh-session"]


def test_prune_stale_subdirs_removes_empty_project_dirs(tmp_path: Path) -> None:
    """所有子目录过期删除后，空的项目目录也应当被清理。"""
    root = tmp_path / "ephemeral"
    root.mkdir()
    project = root / "my-project"
    _touch_dir(project / "old-session", time.time() - 20 * 86400)

    egent.ephemeral_dirs.prune_stale_subdirs(root, max_age_days=10)

    assert not any(root.iterdir())


def test_prune_stale_subdirs_noop_within_age(tmp_path: Path) -> None:
    """所有子目录都在期限内时不应删除。"""
    root = tmp_path / "ephemeral"
    root.mkdir()
    project = root / "my-project"
    project.mkdir()
    _touch_dir(project / "recent-session", time.time() - 100)

    egent.ephemeral_dirs.prune_stale_subdirs(root, max_age_days=10)

    remaining = sorted(p.name for p in project.iterdir())
    assert remaining == ["recent-session"]


def test_prune_stale_subdirs_noop_for_missing_root(tmp_path: Path) -> None:
    """根目录不存在时应静默返回。"""
    egent.ephemeral_dirs.prune_stale_subdirs(tmp_path / "missing")


def test_prune_stale_subdirs_ignores_files(tmp_path: Path) -> None:
    """root 下的普通文件应被忽略。"""
    root = tmp_path / "ephemeral"
    root.mkdir()
    (root / "some_file.txt").write_text("hello", encoding="utf-8")

    egent.ephemeral_dirs.prune_stale_subdirs(root, max_age_days=10)

    remaining = sorted(p.name for p in root.iterdir())
    assert remaining == ["some_file.txt"]
