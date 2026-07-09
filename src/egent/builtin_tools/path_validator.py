"""路径权限校验。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

import egent.tool

__all__ = [
    "PathPermissionRule",
    "PathPermissions",
    "get_list_path_permissions_tool",
    "matches_path_patterns",
    "resolve_path",
]

PermissionKind = Literal["discoverable", "readable", "editable"]

_PERMISSION_LABELS: dict[PermissionKind, str] = {
    "discoverable": "可发现",
    "readable": "可读",
    "editable": "可编辑",
}


def resolve_path(path_text: str) -> Path:
    """将路径文本解析为基于当前工作目录的绝对路径。"""
    path_input = Path(path_text.strip())
    if not path_input.is_absolute():
        path_input = Path.cwd() / path_input
    return path_input.resolve()


def matches_path_patterns(relative_text: str, patterns: tuple[str, ...]) -> bool:
    """判断相对路径是否匹配任一 glob 模式（按路径前缀分段匹配）。"""
    normalized_text = relative_text or "."
    if any(PurePosixPath(normalized_text).full_match(pattern) for pattern in patterns):
        return True
    path_segments = PurePosixPath(normalized_text).parts
    for segment_count in range(1, len(path_segments) + 1):
        path_prefix = PurePosixPath(*path_segments[:segment_count])
        if any(path_prefix.full_match(pattern) for pattern in patterns):
            return True
    return False


@dataclass(frozen=True)
class PathPermissionRule:
    """单项路径权限：匹配白名单且不匹配黑名单即允许。"""

    whitelist: tuple[str, ...]
    blacklist: tuple[str, ...] = ()

    def allows(self, relative_text: str | None) -> bool:
        """匹配白名单且不匹配黑名单时返回 True。"""
        if relative_text is None:
            return False
        if not self.whitelist:
            return False
        if not matches_path_patterns(relative_text, self.whitelist):
            return False
        if self.blacklist and matches_path_patterns(relative_text, self.blacklist):
            return False
        return True


@dataclass(frozen=True)
class PathPermissions:
    """路径权限配置：可发现、可读、可编辑各一组白名单与黑名单。"""

    root: Path
    discoverable: PathPermissionRule
    readable: PathPermissionRule
    editable: PathPermissionRule

    def relative_posix(self, path: Path) -> str | None:
        """返回 path 相对 root 的 posix 路径；不在 root 内时返回 None。"""
        try:
            relative = path.resolve().relative_to(self.root.resolve())
        except ValueError:
            return None
        if relative.parts:
            return relative.as_posix()
        return "."

    def is_discoverable(self, path: Path) -> bool:
        """路径是否允许被遍历发现。"""
        return self.discoverable.allows(self.relative_posix(path))

    def is_readable(self, path: Path) -> bool:
        """路径是否允许读取。"""
        return self.readable.allows(self.relative_posix(path))

    def is_editable(self, path: Path) -> bool:
        """路径是否允许写入或修改。"""
        return self.editable.allows(self.relative_posix(path))

    def is_searchable(self, path: Path) -> bool:
        """目录搜索等价于可发现且可读。"""
        return self.is_discoverable(path) and self.is_readable(path)

    def format_rules(self) -> str:
        """格式化输出三项权限的白名单与黑名单。"""
        root_text = self.root.resolve().as_posix()
        lines = [f"根目录: {root_text}", ""]
        for permission_kind in ("discoverable", "readable", "editable"):
            rule = getattr(self, permission_kind)
            label = _PERMISSION_LABELS[permission_kind]
            lines.append(f"{label}:")
            lines.append(f"  白名单: {_format_pattern_list(rule.whitelist)}")
            lines.append(f"  黑名单: {_format_pattern_list(rule.blacklist)}")
            lines.append("")
        lines.append("目录搜索: 可发现且可读")
        lines.append("文件搜索: 可读")
        return "\n".join(lines)


def _format_pattern_list(patterns: tuple[str, ...]) -> str:
    if not patterns:
        return "(无)"
    return ", ".join(patterns)


def get_list_path_permissions_tool(
    permissions: PathPermissions,
    name: str = "list_path_permissions",
    description: str | None = None,
) -> egent.tool.ToolCallable:
    """生成列出路径权限白名单与黑名单的内置工具。"""
    tool_description = description or "列出当前路径权限规则（可发现、可读、可编辑的白名单与黑名单）"

    def list_path_permissions() -> str:
        return permissions.format_rules()

    list_path_permissions.__name__ = name
    list_path_permissions.__doc__ = tool_description
    return list_path_permissions
