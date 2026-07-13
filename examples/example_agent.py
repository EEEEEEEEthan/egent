"""egent 聊天 CLI 示例。

运行前请在**当前工作目录**配置 ``.egent/.model.toml``::

    pip install -e .
    python examples/example_agent.py
"""

from __future__ import annotations

from pathlib import Path

import _common
import conversation_printer
from egent import builtin_tools
from egent.agent import Agent

_EXAMPLE_GREET_SKILL = Path(__file__).resolve().parent.parent / ".agents" / "skills" / "example-greet"


async def run_turn(
    agent: Agent,
    printer: conversation_printer.ConversationPrinter,
) -> None:
    """运行一轮交互：收集用户输入并发送请求。"""
    agent.add_message("user", input(">>> ").strip())
    await printer.request()


async def async_main() -> int:
    """运行交互式聊天，返回进程退出码。"""
    agent = Agent(
        "gpt5",
        skills=[_EXAMPLE_GREET_SKILL],
        tools=[
            *builtin_tools.git_tools.read_only_tools,
            builtin_tools.git_tools.git_add,
            builtin_tools.git_tools.git_commit,
            _common.reload_modules,
        ],
        path_permissions=_common.create_egent_path_permissions(),
    )
    printer = conversation_printer.ConversationPrinter(agent)
    while True:
        await run_turn(agent, printer)


if __name__ == "__main__":
    _common.run_cli(async_main)
