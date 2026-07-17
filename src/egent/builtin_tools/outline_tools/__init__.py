"""outline_tools 包：文件大纲解析工具。"""

from __future__ import annotations

import egent.builtin_tools.outline_tools._base as _outline_base
import egent.builtin_tools.outline_tools._cs as _outline_cs
import egent.builtin_tools.outline_tools._gd as _outline_gd
import egent.builtin_tools.outline_tools._md as _outline_md
import egent.builtin_tools.outline_tools._py as _outline_py


def get_parser(
    suffix: str,
) -> type[_outline_base.OutlineParser] | None:
    """工厂函数，根据文件后缀返回对应的 OutlineParser 类，无匹配返回 None。"""
    suffix_lower = suffix.lower()
    for parser_cls in (
        _outline_cs.CsOutlineParser,
        _outline_gd.GdOutlineParser,
        _outline_md.MdOutlineParser,
        _outline_py.PyOutlineParser,
    ):
        if suffix_lower in parser_cls.supported_suffixes:
            return parser_cls
    return None
