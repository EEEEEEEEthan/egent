"""egent 聊天 CLI 示例。

运行前请在**当前工作目录**配置 ``.egent/.model.toml``::

    python examples/example_agent.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import _bootstrap  # noqa: F401  # pylint: disable=unused-import  # 必须在 import egent 之前

import studio

import egent.agent
import egent.builtin_tools.path_validator

_WORKING_DIRECTORY = Path.cwd().resolve().as_posix()
_DISCOVERABLE_RULE = egent.builtin_tools.path_validator.PathPermissionRule(
    whitelist=("*",),
    blacklist=(
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
    ),
)
_READABLE_RULE = egent.builtin_tools.path_validator.PathPermissionRule(
    whitelist=("*",),
    blacklist=(f"{_WORKING_DIRECTORY}/.egent/.model.toml",),
)
_NO_EDITABLE_RULE = egent.builtin_tools.path_validator.PathPermissionRule(
    whitelist=(),
    blacklist=("*",),
)


async def async_main() -> int:
    """运行交互式聊天，返回进程退出码。"""
    studio_instance = studio.Studio()

    ethan = egent.agent.Agent(
        name="ethan",
        settings="gpt5",
        system_prompt=
            "你是ethan，你是这个项目的主程\n"
            "milo是你的助理，如果需要看代码，尽量和milo说让他先看，帮你筛选出关键代码，然后你再去看.尽量不要直接看,这会耽误你太多时间\n"
            "这是群聊,所以你不必把别人的话复述给用户\n"
            "用户是资深程序员,也是制作人,所以你和用户沟通的时候不需要解释太多\n"
        ,
        skills=(),
        tools=(studio_instance.get_speak_tool("ethan"),),
        path_permissions=egent.builtin_tools.path_validator.PathPermissions(
            discoverable=_DISCOVERABLE_RULE,
            readable=_READABLE_RULE,
            editable=_NO_EDITABLE_RULE,
        ),
    )
    studio_instance.add(ethan)

    milo = egent.agent.Agent(
        name="milo",
        settings="gpt5",
        system_prompt=
            "你是milo，是ethan的助理。ethan是这个项目的主程\n"
        ,
        skills=(),
        tools=(studio_instance.get_speak_tool("milo"),),
        path_permissions=egent.builtin_tools.path_validator.PathPermissions(
            discoverable=_DISCOVERABLE_RULE,
            readable=_READABLE_RULE,
            editable=_NO_EDITABLE_RULE,
        ),
    )
    studio_instance.add(milo)

    while True:
        user_input = input(">>> ").strip()
        ethan.add_message("user", f"用户:\n{user_input}")
        ethan_reply = await ethan.send()
        if ethan_reply:
            studio.print_speech("ethan", ethan_reply)
        await studio_instance.await_idle()

if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
