"""记忆系统内置工具（不走 PathPermissions）。"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_logger = logging.getLogger(__name__)

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00]')
_TIMESTAMP_LINE_RE = re.compile(r'^>\s*timestamp:\s*(.*)', re.IGNORECASE)


def _prepend_timestamp(content: str) -> str:
    return f"> timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n{content}"


def _parse_timestamp(content: str) -> str | None:
    """从内容首行解析时间戳，成功返回时间文本，失败返回 None。"""
    first_line = content.splitlines()[0] if content.splitlines() else ""
    match = _TIMESTAMP_LINE_RE.match(first_line)
    return match.group(1).strip() if match else None


@dataclass
class MemoryToolSet:
    """基于 agent_name 的记忆系统工具集。"""

    agent_name: str

    @property
    def __memory_dir(self) -> Path:
        return Path.cwd() / ".egent" / ".memories" / self.agent_name

    def memory_remember(self, title: str, content: str) -> str:
        """新建一条记忆。

        @param title 记忆标题（非法字符将替换为 _）
        @param content 记忆内容（Markdown 格式文档）
        """
        memory_dir = self.__memory_dir
        memory_dir.mkdir(parents=True, exist_ok=True)
        file_path = memory_dir / f"{_INVALID_FILENAME_CHARS.sub('_', title)}.md"
        if file_path.exists():
            raise FileExistsError(f"记忆已存在：{title}")
        file_path.write_text(_prepend_timestamp(content), encoding="utf-8")
        return f"已创建记忆：{title}"

    def memory_recall(self, pattern: str) -> str:
        """正则搜索记忆目录下所有内容，返回匹配列表。

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
            try:
                content = md_file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                import traceback  # pylint: disable=import-outside-toplevel
                _logger.warning("读取记忆文件失败 %s:\n%s", md_file, traceback.format_exc().rstrip())
                continue
            ts = _parse_timestamp(content) or "很久以前"
            if regex.search(md_file.name):
                matched.append(f"[{ts}] (文件名匹配)")
            for line in content.splitlines():
                if regex.search(line):
                    matched.append(f"[{ts}] {line}")
        return "\n".join(matched) if matched else "(无匹配)"

    def memory_update(self, title: str, content: str) -> str:
        """覆盖写入一条记忆。

        @param title 记忆标题
        @param content 记忆内容（Markdown 格式文档）
        """
        file_path = self.__memory_dir / f"{_INVALID_FILENAME_CHARS.sub('_', title)}.md"
        if not file_path.exists():
            raise FileNotFoundError(f"记忆不存在：{title}")
        file_path.write_text(_prepend_timestamp(content), encoding="utf-8")
        return f"已更新记忆：{title}"

    def memory_forget(self, title: str) -> str:
        """删除一条记忆。

        @param title 记忆标题
        """
        file_path = self.__memory_dir / f"{_INVALID_FILENAME_CHARS.sub('_', title)}.md"
        if not file_path.exists():
            raise FileNotFoundError(f"记忆不存在：{title}")
        file_path.unlink()
        return f"已删除记忆：{title}"

    def memory_read(self, title: str) -> str:
        """按标题读取完整 .md 内容返回。

        @param title 记忆标题
        """
        file_path = self.__memory_dir / f"{_INVALID_FILENAME_CHARS.sub('_', title)}.md"
        if not file_path.exists():
            raise FileNotFoundError(f"记忆不存在：{title}")
        content = file_path.read_text(encoding="utf-8")
        ts = _parse_timestamp(content)
        if ts is not None:
            return "\n".join([ts, *content.splitlines()[1:]])
        return f"很久以前\n{content}"

    @property
    def list_titles(self) -> list[str]:
        """返回排序后的 .md 文件名（不含后缀），无文件返回空列表。"""
        if not (d := self.__memory_dir).is_dir():
            return []
        return sorted(f.stem for f in d.glob("*.md") if f.is_file())

    @property
    def tools(self) -> tuple:
        """全部记忆系统工具。"""
        return (self.memory_remember, self.memory_recall, self.memory_update, self.memory_forget, self.memory_read)
