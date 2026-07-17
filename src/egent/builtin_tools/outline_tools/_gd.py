"""GDScript 大纲解析器：class_name/extends/const/var/@onready var/signal/func 定义行 + 紧跟定义前的 # 注释连续行。"""

from __future__ import annotations

import re

import egent.builtin_tools.outline_tools._base as _outline_base

_KEYWORD_DEF = re.compile(
    r"^\s*(?:class_name|extends|const|@?onready\s+var|var|signal|func)\b"
)


class GdOutlineParser(_outline_base.OutlineParser):
    """GDScript 文件大纲解析器。"""

    supported_suffixes = [".gd"]

    @staticmethod
    def parse_lines(lines: list[str]) -> str:
        result: list[str] = []
        stripped = [line.rstrip("\n\r") for line in lines]
        i = 0
        while i < len(stripped):
            if _KEYWORD_DEF.search(stripped[i]):
                j = i - 1
                while j >= 0 and stripped[j].strip().startswith("#"):
                    j -= 1
                for k in range(j + 1, i):
                    result.append(f"行{k + 1}: {stripped[k].strip()}")
                result.append(f"行{i + 1}: {stripped[i].strip()}")
            i += 1
        return "\n".join(result) if result else "(无大纲)"
