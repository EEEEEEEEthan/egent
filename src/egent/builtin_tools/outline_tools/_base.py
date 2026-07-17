"""OutlineParser 基类。"""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import ClassVar

_logger = logging.getLogger(__name__)


class OutlineParser:
    """文件大纲解析器基类。"""

    supported_suffixes: ClassVar[list[str]] = []

    def parse(self, text: str) -> str:
        """解析文本返回大纲，失败返回"解析失败"。"""
        try:
            return self.parse_lines(text.splitlines())
        except Exception:  # pylint: disable=broad-exception-caught
            import traceback  # pylint: disable=import-outside-toplevel
            tb = traceback.format_exc().rstrip()
            _logger.error("大纲解析失败:\n%s", tb)
            return f"解析失败\n{tb}"

    @staticmethod
    @abstractmethod
    def parse_lines(lines: list[str]) -> str:
        """纯文本解析入口，子类必须实现。"""
