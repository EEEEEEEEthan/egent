"""Markdown 大纲解析器：各级标题行 # ~ ######。"""

from __future__ import annotations

import re

import egent.builtin_tools.outline_tools._base as _outline_base

_HEADING = re.compile(r"^#{1,6}\s")


class MdOutlineParser(_outline_base.OutlineParser):
    """Markdown 文件大纲解析器。"""

    supported_suffixes = [".md"]

    @staticmethod
    def parse_lines(lines: list[str]) -> str:
        result: list[str] = []
        for i, line in enumerate(lines, 1):
            s = line.rstrip("\n\r")
            if _HEADING.search(s):
                result.append(f"行{i}: {s.strip()}")
        return "\n".join(result) if result else "(无大纲)"
