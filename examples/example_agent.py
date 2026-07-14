"""egent 聊天 CLI 示例。

运行前请在**当前工作目录**配置 ``.egent/.model.toml``::

    python examples/example_agent.py
"""

from __future__ import annotations

import asyncio

import _bootstrap  # noqa: F401  # pylint: disable=unused-import  # 必须在 import egent 之前

import studio


async def async_main() -> int:
    """运行交互式聊天，返回进程退出码。"""
    studio_instance = studio.Studio()

    while True:
        try:
            user_input = input(">>> ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            return 0
        if not user_input:
            continue
        await studio_instance.send(user_input)

if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
