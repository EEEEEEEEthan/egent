"""egent 聊天 CLI 示例。

运行前请在**当前工作目录**配置 ``.egent/.model.toml``::

    python examples/example_agent.py
"""

from __future__ import annotations

import _bootstrap  # noqa: F401  # 必须在 import egent 之前

import asyncio
from pathlib import Path

import conversation_printer
import egent.agent
import egent.builtin_tools.path_validator
import egent.tool

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
    def get_speak_tool(from_name: str):
        @egent.tool.end_conversation
        async def speak_tool(to_names: list[str], prompt: str) -> str:
            """对指定角色说话，并得到回复
            @param to_names: 说话对象（可多个）
            @param prompt: 说话内容
            @return: 回复内容
            """
            targets = set(to_names)
            target_label = ", ".join(to_names)
            print(f"{from_name}->{target_label}:\n{prompt}")
            for agent in agents.values():
                if agent.name in targets:
                    agent.add_message("system", f"{from_name}对你说:\n{prompt}")
                elif agent.name != from_name:
                    agent.add_message("system", f"{from_name}对{target_label}说:\n{prompt}")
            results: dict[str, str] = {}
            for agent in agents.values():
                if agent.name in targets:
                    results[agent.name] = await agent.send()
            for name, result in results.items():
                print(f"{name}->{from_name}:\n{result}")
            for agent in agents.values():
                if agent.name not in targets and agent.name != from_name:
                    for name, result in results.items():
                        agent.add_message("system", f"{name}回复{from_name}:\n{result}")
            return "\n\n".join(f"{name}: {result}" for name, result in results.items())
        return speak_tool
    # ethan
    ethan = egent.agent.Agent(
        name="ethan",
        settings="gpt5",
        system_prompt=
            "你是ethan，你是这个项目的主程\n"
            "milo是你的助理，如果需要看代码，尽量和milo说让他先看，帮你筛选出关键代码，然后你再去看.尽量不要直接看,这会耽误你太多时间"
        ,
        skills=(),
        tools=(get_speak_tool("ethan"),),
        path_permissions=egent.builtin_tools.path_validator.PathPermissions(
            discoverable=_DISCOVERABLE_RULE,
            readable=_READABLE_RULE,
            editable=_NO_EDITABLE_RULE,
        ),
    )
    agents[ethan.name] = ethan
    # milo
    milo = egent.agent.Agent(
        name="milo",
        settings="gpt5",
        system_prompt=
            "你是milo，是ethan的助理。ethan是这个项目的主程\n"
        ,
        skills=(),
        tools=(get_speak_tool("milo"),),
        path_permissions=egent.builtin_tools.path_validator.PathPermissions(
            discoverable=_DISCOVERABLE_RULE,
            readable=_READABLE_RULE,
            editable=_NO_EDITABLE_RULE,
        ),
    )
    agents[milo.name] = milo
    conversation_printer.ConversationPrinter(ethan)
    conversation_printer.ConversationPrinter(milo, 1)
    while True:
        ethan.add_message("user", input(">>> ").strip())
        print(f"ethan: \n{await ethan.send()}")

if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
