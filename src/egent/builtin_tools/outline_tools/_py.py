"""Python 大纲解析器：class/def/常量赋值(全大写)行 + 三引号 docstring 行（含开闭）。"""

from __future__ import annotations

import re

import egent.builtin_tools.outline_tools._base as _outline_base

_CLASS_DEF = re.compile(r"^\s*class\s+\w+")
_FUNC_DEF = re.compile(r"^\s*def\s+\w+")
_CONST_ASSIGN = re.compile(r"^\s*[A-Z][A-Z0-9_]*\s*(?::[^=]*)?\s*=")
_TRIPLE_QUOTE = re.compile(r'"""|\'\'\'')


class PyOutlineParser(_outline_base.OutlineParser):
    """Python 文件大纲解析器。"""

    supported_suffixes = [".py"]

    @staticmethod
    def parse_lines(lines: list[str]) -> str:
        result: list[str] = []
        for i, line in enumerate(lines, 1):
            s = line.rstrip("\n\r")
            if _CLASS_DEF.search(s) or _FUNC_DEF.search(s) or _CONST_ASSIGN.search(s) or _TRIPLE_QUOTE.search(s):
                result.append(f"行{i}: {s.strip()}")
        return "\n".join(result) if result else "(无大纲)"
