"""egent 聊天 CLI 示例。

运行前请在**当前工作目录**配置 ``.egent/.model.toml``::

    pip install -e .
    python examples/example_agent.py
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

import conversation_printer
import egent.agent
import egent.builtin_tools.path_validator

_EXAMPLE_GREET_SKILL = Path(__file__).resolve().parent.parent / ".agents" / "skills" / "example-greet"

async def run_turn(
    agent: egent.agent.Agent,
    printer: conversation_printer.ConversationPrinter,
) -> None:
    """运行一轮交互：收集用户输入并发送请求。"""
    agent.add_message("user", input(">>> ").strip())
    await printer.send()

async def async_main() -> int:
    """运行交互式聊天，返回进程退出码。"""
    ethan = egent.agent.Agent(
        settings="gpt5",
        system_prompt="你是ethan，你是这个项目的主程",
        skills=[_EXAMPLE_GREET_SKILL],
        tools=(),
        path_permissions=egent.builtin_tools.path_validator.PathPermissions(
            discoverable=egent.builtin_tools.path_validator.PathPermissionRule(
                whitelist=("*",),
                blacklist=(),
            ),
            readable=egent.builtin_tools.path_validator.PathPermissionRule(
                whitelist=("*",),
                blacklist=(),
            ),
            editable=egent.builtin_tools.path_validator.PathPermissionRule(
                whitelist=("*",),
                blacklist=("*",),
            ),
        ),
    )
    printer = conversation_printer.ConversationPrinter(ethan)
    while True:
        await run_turn(ethan, printer)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
