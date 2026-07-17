"""C# 大纲解析器：class/struct/interface/enum/const/field/property/method 定义行 + /// 三斜线注释行。"""

from __future__ import annotations

import re

import egent.builtin_tools.outline_tools._base as _outline_base

# 类型定义：class/struct/interface/enum/record + 名称
_TYPE_DEF = re.compile(r"^\s*(?:\w+\s+)*\b(?:class|struct|interface|enum|record)\s+\w+")
# 成员定义：包含 const/field/property/method 特征
_MEMBER_DEF = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|static|virtual|override|abstract|"
    r"sealed|readonly|async|unsafe|partial|new|const|extern|implicit|explicit)\s+)*"
    r"\w+(?:<[^>]+>)?(?:\[\])*\s+\w+\s*(?:[({;=]|=>)"
)
_TRIPLE_SLASH = re.compile(r"^\s*///")


class CsOutlineParser(_outline_base.OutlineParser):
    """C# 文件大纲解析器。"""

    supported_suffixes = [".cs"]

    @staticmethod
    def parse_lines(lines: list[str]) -> str:
        result: list[str] = []
        for i, line in enumerate(lines, 1):
            s = line.rstrip("\n\r")
            if _TYPE_DEF.search(s) or _TRIPLE_SLASH.search(s) or _MEMBER_DEF.search(s):
                result.append(f"行{i}: {s.strip()}")
        return "\n".join(result) if result else "(无大纲)"
