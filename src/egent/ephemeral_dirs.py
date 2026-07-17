"""系统临时目录容量维护。"""

from __future__ import annotations

import pathlib
import shutil
import time


def prune_stale_subdirs(root: pathlib.Path, max_age_days: int = 10) -> None:
    """遍历 root 下所有子目录（递归两层），删除超过 max_age_days 天未修改的子目录。"""
    if not root.is_dir():
        return
    cutoff = time.time() - max_age_days * 86400
    for project_hash_dir in root.iterdir():
        if not project_hash_dir.is_dir():
            continue
        for guid_dir in project_hash_dir.iterdir():
            if guid_dir.is_dir() and guid_dir.stat().st_mtime < cutoff:
                shutil.rmtree(guid_dir, ignore_errors=True)
        if not any(project_hash_dir.iterdir()):
            shutil.rmtree(project_hash_dir, ignore_errors=True)
