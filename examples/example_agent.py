"""egent 聊天 CLI 示例。

运行前请在**当前工作目录**配置 ``.egent/.model.toml``::

    python examples/example_agent.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import _bootstrap  # noqa: F401  # pylint: disable=unused-import  # 必须在 import egent 之前

import conversation_printer
import egent.agent
import egent.builtin_tools.path_validator

_WORKING_DIRECTORY = Path.cwd().resolve().as_posix()
_DISCOVERABLE_RULE = egent.builtin_tools.path_validator.PathPermissionRule(
    whitelist=("*",),
    blacklist=(
        f"{_WORKING_DIRECTORY}/.git",
        f"{_WORKING_DIRECTORY}/.git/*",
        f"{_WORKING_DIRECTORY}/**/__pycache__",
        f"{_WORKING_DIRECTORY}/**/__pycache__/*",
        f"{_WORKING_DIRECTORY}/**/.pytest_cache",
        f"{_WORKING_DIRECTORY}/**/.pytest_cache/*",
        f"{_WORKING_DIRECTORY}/**/.ruff_cache",
        f"{_WORKING_DIRECTORY}/**/.ruff_cache/*",
    ),
)
_READABLE_RULE = egent.builtin_tools.path_validator.PathPermissionRule(
    whitelist=("*",),
    blacklist=(f"{_WORKING_DIRECTORY}/.egent/.model.toml",),
)
_EDITABLE_RULE = egent.builtin_tools.path_validator.PathPermissionRule(
    whitelist=(f"{_WORKING_DIRECTORY}/*",),
    blacklist=(
        f"{_WORKING_DIRECTORY}/.git",
        f"{_WORKING_DIRECTORY}/.git/*",
        f"{_WORKING_DIRECTORY}/.egent",
        f"{_WORKING_DIRECTORY}/.egent/*",
        f"{_WORKING_DIRECTORY}/.egent/.model.toml",
        f"{_WORKING_DIRECTORY}/**/__pycache__",
        f"{_WORKING_DIRECTORY}/**/__pycache__/*",
        f"{_WORKING_DIRECTORY}/**/.pytest_cache",
        f"{_WORKING_DIRECTORY}/**/.pytest_cache/*",
        f"{_WORKING_DIRECTORY}/**/.ruff_cache",
        f"{_WORKING_DIRECTORY}/**/.ruff_cache/*",
    ),
)


async def async_main() -> int:
    """运行交互式聊天，返回进程退出码。"""
    agent = egent.agent.Agent(
        name="ethan",
        settings="gpt5",
        system_prompt=(
            "你是ethan，你是这个项目的主程\n"
            "用户是资深程序员，也是制作人，沟通时不需要解释太多\n"
        ),
    )
    agent.path_permissions = egent.builtin_tools.path_validator.PathPermissions(
        discoverable=_DISCOVERABLE_RULE,
        readable=_READABLE_RULE,
        editable=_EDITABLE_RULE,
    )
    with conversation_printer.ConversationPrinter(agent):
        while True:
            try:
                user_input = input(">>> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not user_input:
                continue
            agent.add_message("user", user_input)
            await agent.send()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
