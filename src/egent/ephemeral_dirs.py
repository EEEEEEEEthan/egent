"""``.egent/.temp`` 与 ``.egent/.logs`` 等临时目录的容量维护。"""
# pylint: disable=protected-access

from __future__ import annotations

import pathlib

import egent._constants


def prune_oldest_files_in_directory(
    directory: pathlib.Path,
    max_files: int = egent._constants.EPHEMERAL_DIR_MAX_FILES,
) -> None:
    """删除目录中最旧的普通文件，使文件数量不超过 ``max_files``。"""
    if not directory.is_dir():
        return

    files = [path for path in directory.iterdir() if path.is_file()]
    excess_file_count = len(files) - max_files
    if excess_file_count <= 0:
        return

    files.sort(key=lambda path: (path.stat().st_mtime, path.name))
    for path in files[:excess_file_count]:
        path.unlink(missing_ok=True)
