"""路径权限校验。"""

from __future__ import annotations

from pathlib import Path
import abc

__all__ = ["PathValidator", "resolve_path"]


def resolve_path(path_text: str) -> Path:
    """将路径文本解析为基于当前工作目录的绝对路径。"""
    path_input = Path(path_text.strip())
    if not path_input.is_absolute():
        path_input = Path.cwd() / path_input
    return path_input.resolve()


class PathValidator(abc.ABC):
    """按可发现、可读、可编辑与忽略规则校验路径权限。"""

    def is_discoverable(self, path: Path) -> bool:
        """路径是否允许被遍历或搜索发现。"""
        return self._is_discoverable(path)

    def is_readable(self, path: Path) -> bool:
        """路径是否允许读取。"""
        return self._is_readable(path)

    def is_editable(self, path: Path) -> bool:
        """路径是否允许写入或修改。"""
        return self._is_editable(path)

    def is_searchable(self, path: Path) -> bool:
        """路径是否允许参与内容搜索。"""
        return self.is_discoverable(path) and self.is_readable(path) and self._is_searchable(path)

    @abc.abstractmethod
    def _is_discoverable(self, path: Path) -> bool:
        ...

    @abc.abstractmethod
    def _is_readable(self, path: Path) -> bool:
        ...

    @abc.abstractmethod
    def _is_editable(self, path: Path) -> bool:
        ...

    @abc.abstractmethod
    def _is_searchable(self, path: Path) -> bool:
        ...
