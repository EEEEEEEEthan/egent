"""OutlineParser 基类。"""

from __future__ import annotations

from abc import abstractmethod
from typing import ClassVar


class OutlineParser:
    """文件大纲解析器基类。"""

    supported_suffixes: ClassVar[list[str]] = []

    def parse(self, text: str) -> str:
        """解析文本返回大纲，失败返回"解析失败"。"""
        try:
            return self.parse_lines(text.splitlines())
        except Exception:  # pylint: disable=broad-exception-caught
            return "解析失败"

    @staticmethod
    @abstractmethod
    def parse_lines(lines: list[str]) -> str:
        """纯文本解析入口，子类必须实现。"""
