"""环境信息内置工具。"""

from __future__ import annotations

from datetime import datetime, timezone


class EnvToolSet:
    """环境信息工具集。"""

    def get_current_time(self) -> str:
        """获取当前时间与时区。

        @return 当前时间+时区，格式 YYYY-MM-DD HH:MM:SS
        """
        return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

    @property
    def tools(self) -> tuple:
        """全部环境信息工具。"""
        return (self.get_current_time,)
