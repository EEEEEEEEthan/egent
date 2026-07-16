"""工具结果长度与其它运行时限制。"""

from __future__ import annotations

import pathlib
import shutil

TOOL_RESULT_MAX_CHARS = 8_000
EPHEMERAL_DIR_MAX_FILES = 128
SEARCH_FILE_TIMEOUT_SECONDS = 10
SEARCH_DIRECTORY_TIMEOUT_SECONDS = 30

EGENT_DIR = pathlib.Path.cwd() / ".egent"
EGENT_GITIGNORE_ENTRIES = (".model.toml", "/.temp/", "/.logs/", "*/memories/")
EGENT_GITIGNORE_DEPRECATED = (".memory/", "*/memory/")


def ensure_egent_gitignore() -> None:
    """确保 ``.egent/.gitignore`` 包含模型配置与临时目录忽略项。"""
    EGENT_DIR.mkdir(parents=True, exist_ok=True)

    # 迁移旧版记忆目录 .memory/ → .memories/
    old_memory_dir = EGENT_DIR / ".memory"
    new_memory_dir = EGENT_DIR / ".memories"
    if old_memory_dir.is_dir():
        if new_memory_dir.is_dir():
            shutil.copytree(old_memory_dir, new_memory_dir, dirs_exist_ok=True)
            shutil.rmtree(old_memory_dir)
        else:
            old_memory_dir.rename(new_memory_dir)

    gitignore_path = EGENT_DIR / ".gitignore"
    if not gitignore_path.is_file():
        gitignore_path.write_text(
            "\n".join(EGENT_GITIGNORE_ENTRIES) + "\n",
            encoding="utf-8",
        )
        return
    existing_lines = gitignore_path.read_text(encoding="utf-8").splitlines()
    # 移除废弃条目
    existing_lines = [l for l in existing_lines if l not in EGENT_GITIGNORE_DEPRECATED]
    missing_entries = [
        entry for entry in EGENT_GITIGNORE_ENTRIES if entry not in existing_lines
    ]
    if not missing_entries:
        return
    gitignore_path.write_text(
        "\n".join(existing_lines + missing_entries) + "\n",
        encoding="utf-8",
    )
