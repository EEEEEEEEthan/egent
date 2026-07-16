"""记忆系统内置工具（不走 PathPermissions）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00]')


@dataclass
class MemoryToolSet:
    """基于 agent_name 的记忆系统工具集。"""

    agent_name: str

    @property
    def __memory_dir(self) -> Path:
        return Path.cwd() / ".egent" / self.agent_name / "memory"

    def remember(self, title: str, content: str) -> str:
        """新建一条记忆。

        @param title 记忆标题（非法字符将替换为 _）
        @param content 记忆内容
        """
        memory_dir = self.__memory_dir
        memory_dir.mkdir(parents=True, exist_ok=True)
        file_path = memory_dir / f"{_INVALID_FILENAME_CHARS.sub('_', title)}.md"
        if file_path.exists():
            raise FileExistsError(f"记忆已存在：{title}")
        file_path.write_text(content, encoding="utf-8")
        return f"已创建记忆：{title}"

    def recall(self, pattern: str) -> str:
        """正则搜索记忆目录下所有 .md 文件名+内容，返回匹配列表。

        @param pattern 正则表达式
        """
        try:
            regex = re.compile(pattern)
        except re.error as e:
            raise ValueError(f"无效的正则表达式：{e}") from e

        memory_dir = self.__memory_dir
        if not memory_dir.is_dir():
            return "(无匹配)"

        matched: list[str] = []
        for md_file in sorted(memory_dir.glob("*.md")):
            if not md_file.is_file():
                continue
            name = md_file.name
            if regex.search(name):
                matched.append(f"[{name}] (文件名匹配)")
            try:
                for i, line in enumerate(md_file.read_text(encoding="utf-8").splitlines(), 1):
                    if regex.search(line):
                        matched.append(f"[{name} line{i}] {line}")
            except (UnicodeDecodeError, OSError):
                continue
        return "\n".join(matched) if matched else "(无匹配)"

    def update_memory(self, title: str, content: str) -> str:
        """覆盖写入一条记忆。

        @param title 记忆标题
        @param content 记忆内容
        """
        file_path = self.__memory_dir / f"{_INVALID_FILENAME_CHARS.sub('_', title)}.md"
        if not file_path.exists():
            raise FileNotFoundError(f"记忆不存在：{title}")
        file_path.write_text(content, encoding="utf-8")
        return f"已更新记忆：{title}"

    def forget(self, title: str) -> str:
        """删除一条记忆。

        @param title 记忆标题
        """
        file_path = self.__memory_dir / f"{_INVALID_FILENAME_CHARS.sub('_', title)}.md"
        if not file_path.exists():
            raise FileNotFoundError(f"记忆不存在：{title}")
        file_path.unlink()
        return f"已删除记忆：{title}"

    @property
    def tools(self) -> tuple:
        """全部记忆系统工具。"""
        return (self.remember, self.recall, self.update_memory, self.forget)
