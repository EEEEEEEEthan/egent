"""examples 包：提供热重载功能。"""

from __future__ import annotations

import importlib
import sys

import _bootstrap  # noqa: F401  # pylint: disable=unused-import  # 必须在 import egent 之前
import egent.agent


def hot_reload(leader):
    """全工程 hot reload：按模块层级深度降序 reload 所有 egent 和 examples 相关模块。"""
    for _, module in sorted(
        (
            (name.count("."), module)
            for name, module in sys.modules.items()
            if name.startswith(("egent.", "examples.")) or name in ("egent", "examples")
        ),
        key=lambda x: x[0],
        reverse=True,
    ):
        try:
            importlib.reload(module)
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    leader.__class__ = egent.agent.Agent
