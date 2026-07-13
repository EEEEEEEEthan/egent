"""egent 聊天 CLI 示例。

运行前请在**当前工作目录**配置 ``.egent/.model.toml``::

    pip install -e .
    python examples/example_agent.py
"""

from __future__ import annotations

import asyncio
import importlib
from inspect import _void
import sys
from pathlib import Path

import conversation_printer
import egent.agent
import egent.builtin_tools.path_validator

_EXAMPLE_GREET_SKILL = Path(__file__).resolve().parent.parent / ".agents" / "skills" / "example-greet"

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
_EDITABLE_RULE = egent.builtin_tools.path_validator.PathPermissionRule(
    whitelist=(
        f"{_WORKING_DIRECTORY}",
        f"{_WORKING_DIRECTORY}/*",
    ),
    blacklist=(),
)
_NO_EDITABLE_RULE = egent.builtin_tools.path_validator.PathPermissionRule(
    whitelist=(),
    blacklist=("*",),
)

async def async_main() -> int:
    """运行交互式聊天，返回进程退出码。"""
    agents: dict[str, egent.agent.Agent] = {}
    ethan = egent.agent.Agent(
        settings="gpt5",
        system_prompt=
            "你是ethan，你是这个项目的主程\n"
        ,
        skills=(),
        tools=(),
        path_permissions=egent.builtin_tools.path_validator.PathPermissions(
            discoverable=_DISCOVERABLE_RULE,
            readable=_READABLE_RULE,
            editable=_NO_EDITABLE_RULE,
        ),
    )
    ethan.name = "ethan"
    agents[ethan.name] = ethan
    milo = egent.agent.Agent(
        settings="gpt5",
        system_prompt=
            "你是milo，你是ethan的小弟，按ethan的安排做事\n"
        ,
        skills=(),
        tools=(),
        path_permissions=egent.builtin_tools.path_validator.PathPermissions(
            discoverable=_DISCOVERABLE_RULE,
            readable=_READABLE_RULE,
            editable=_NO_EDITABLE_RULE,
        ),
    )
    milo.name = "milo"
    agents[milo.name] = milo
    printer = conversation_printer.ConversationPrinter(ethan)
    while True:
        ethan.add_message("user", input(">>> ").strip())
        await printer.send()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
