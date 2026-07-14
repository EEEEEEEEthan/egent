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

_RESET = "\033[0m"
_RED = "\033[31m"
_WHITE = "\033[37m"


def _print_speech(speaker: str, body: str) -> None:
    print(f"{_RED}{speaker}{_RESET}:\n{_WHITE}{body}{_RESET}")

async def async_main() -> int:
    """运行交互式聊天，返回进程退出码。"""
    agents: dict[str, egent.agent.Agent] = {}
    pending_speak_tasks: set[asyncio.Task[None]] = set()

    def get_speak_tool(from_name: str):
        @egent.tool.end_conversation
        async def speak_tool(to_names: list[str], prompt: str) -> str:
            """对指定角色说话；回复通过回调异步送达，不阻塞本工具返回
            @param to_names: 说话对象（可多个）
            @param prompt: 说话内容
            @return: 发送确认
            """
            if from_name in to_names:
                raise ValueError(f"不能对自己说话：{from_name}")
            from_agent = agents.get(from_name)
            targets = set[str](to_names)
            target_label = ", ".join(to_names)
            _print_speech(f"{from_name}->{target_label}", prompt)
            for agent in agents.values():
                if agent.name in targets:
                    agent.add_message("system", f"{from_name}对你说:\n{prompt}")
                elif agent.name != from_name:
                    agent.add_message("system", f"{from_name}对{target_label}说:\n{prompt}")

            def on_target_replied(name: str, result: str) -> None:
                _print_speech(f"{name}->{from_name}", result)
                from_agent.add_message("system", f"{name}回复:\n{result}")
                for agent in agents.values():
                    if agent.name not in targets and agent.name != from_name:
                        agent.add_message("system", f"{name}回复{from_name}:\n{result}")

            async def dispatch_speak_round() -> None:
                async def dispatch_target_reply(target_agent: egent.agent.Agent) -> None:
                    try:
                        result = await target_agent.send()
                    except Exception as error:  # pylint: disable=broad-exception-caught
                        result = f"[发送失败] {error}"
                    on_target_replied(target_agent.name, result)

                target_agents = [
                    agent for agent in agents.values()
                    if agent.name in targets
                ]
                await asyncio.gather(
                    *(dispatch_target_reply(agent) for agent in target_agents)
                )
                _print_speech(from_name, await from_agent.send())

            if any(agent.name in targets for agent in agents.values()):
                task = asyncio.create_task(dispatch_speak_round())
                pending_speak_tasks.add(task)
                task.add_done_callback(pending_speak_tasks.discard)
            return "message sent."
        return speak_tool
    # ethan
    ethan = egent.agent.Agent(
        name="ethan",
        settings="gpt5",
        system_prompt=
            "你是ethan，你是这个项目的主程\n"
            "milo是你的助理，如果需要看代码，尽量和milo说让他先看，帮你筛选出关键代码，然后你再去看.尽量不要直接看,这会耽误你太多时间\n"
            "这是群聊,所以你不必把别人的话复述给我\n"
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
    #conversation_printer.ConversationPrinter(ethan)
    #conversation_printer.ConversationPrinter(milo, 1)

    async def await_all_agents_idle() -> None:
        while pending_speak_tasks:
            await asyncio.gather(*tuple(pending_speak_tasks))

    while True:
        ethan.add_message("user", input(">>> ").strip())
        _print_speech("ethan", await ethan.send())
        await await_all_agents_idle()

if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
