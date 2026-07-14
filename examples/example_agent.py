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
    ethan = studio_instance.agents["ethan"]

    while True:
        user_input = input(">>> ").strip()
        ethan.add_message("user", f"用户:\n{user_input}")
        ethan_reply = await ethan.send()
        if ethan_reply:
            studio.Studio.print_speech("ethan", ethan_reply)
        await studio_instance.await_idle()

if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
