"""``.egent`` 临时目录容量维护单元测试。"""

from __future__ import annotations

import os
from pathlib import Path

import egent.ephemeral_dirs


def _touch_file(path: Path, modified_timestamp: float) -> None:
    path.write_text(path.name, encoding="utf-8")
    os.utime(path, (modified_timestamp, modified_timestamp))


def test_prune_keeps_newest_files(tmp_path: Path) -> None:
    directory = tmp_path / "temp"
    directory.mkdir()
    for index in range(5):
        _touch_file(directory / f"file-{index:02d}.txt", float(index))

    egent.ephemeral_dirs.prune_oldest_files_in_directory(directory, max_files=3)

    remaining_names = {path.name for path in directory.iterdir()}
    assert remaining_names == {"file-02.txt", "file-03.txt", "file-04.txt"}


def test_prune_ignores_subdirectories(tmp_path: Path) -> None:
    directory = tmp_path / "temp"
    directory.mkdir()
    (directory / "nested").mkdir()
    for index in range(3):
        _touch_file(directory / f"file-{index}.txt", float(index))

    egent.ephemeral_dirs.prune_oldest_files_in_directory(directory, max_files=1)

    remaining_names = {path.name for path in directory.iterdir()}
    assert remaining_names == {"file-2.txt", "nested"}


def test_prune_noop_when_within_limit(tmp_path: Path) -> None:
    directory = tmp_path / "temp"
    directory.mkdir()
    _touch_file(directory / "only.txt", 1_000.0)

    egent.ephemeral_dirs.prune_oldest_files_in_directory(directory, max_files=128)

    assert list(directory.iterdir()) == [directory / "only.txt"]


def test_prune_noop_for_missing_directory(tmp_path: Path) -> None:
    egent.ephemeral_dirs.prune_oldest_files_in_directory(tmp_path / "missing")
