"""多 Agent 工作室：成员间 speak 工具与异步回合调度。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import _bootstrap  # noqa: F401  # pylint: disable=unused-import

import egent.agent
import egent.builtin_tools.path_validator
import egent.tool


class Studio:  # pylint: disable=too-few-public-methods
    """同一对话空间内的 Agent 集合；成员通过 speak 工具互相对话。"""

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

    def __init__(self) -> None:
        self._agents: dict[str, egent.agent.Agent] = {}
        self._pending_speak_tasks: set[asyncio.Task[None]] = set()

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
            tools=(self._get_speak_tool("ethan"),),
            path_permissions=egent.builtin_tools.path_validator.PathPermissions(
                discoverable=Studio._DISCOVERABLE_RULE,
                readable=Studio._READABLE_RULE,
                editable=Studio._NO_EDITABLE_RULE,
            ),
        )
        self._ethan = ethan
        self._agents[ethan.name] = ethan

        milo = egent.agent.Agent(
            name="milo",
            settings="gpt5",
            system_prompt=
                "你是milo，是ethan的助理。ethan是这个项目的主程\n"
            ,
            skills=(),
            tools=(self._get_speak_tool("milo"),),
            path_permissions=egent.builtin_tools.path_validator.PathPermissions(
                discoverable=Studio._DISCOVERABLE_RULE,
                readable=Studio._READABLE_RULE,
                editable=Studio._NO_EDITABLE_RULE,
            ),
        )
        self._agents[milo.name] = milo

    @staticmethod
    def _print_speech(speaker: str, body: str) -> None:
        print(f"\033[31m{speaker}\033[0m:\n\033[37m{body}\033[0m")

    def _get_speak_tool(self, from_name: str) -> egent.tool.ToolCallable:
        @egent.tool.end_conversation
        async def speak_tool(to_names: list[str], prompt: str) -> str:
            """对指定角色说话；回复通过回调异步送达，不阻塞本工具返回
            @param to_names: 说话对象（可多个）
            @param prompt: 说话内容
            @return: 发送确认
            """
            if from_name in to_names:
                raise ValueError(f"不能对自己说话：{from_name}")
            from_agent = self._agents.get(from_name)
            targets = set[str](to_names)
            target_label = ", ".join(to_names)
            Studio._print_speech(f"{from_name}->{target_label}", prompt)
            for agent in self._agents.values():
                if agent.name in targets:
                    agent.add_message("user", f"{from_name}对你说:\n{prompt}")
                elif agent.name != from_name:
                    agent.add_message("user", f"{from_name}对{target_label}说:\n{prompt}")

            def on_target_replied(name: str, result: str) -> None:
                Studio._print_speech(f"{name}->{from_name}", result)
                from_agent.add_message("user", f"{name}回复:\n{result}")
                for agent in self._agents.values():
                    if agent.name not in targets and agent.name != from_name:
                        agent.add_message("user", f"{name}回复{from_name}:\n{result}")

            async def dispatch_speak_round() -> None:
                async def dispatch_target_reply(target_agent: egent.agent.Agent) -> None:
                    try:
                        result = await target_agent.send()
                    except Exception as error:  # pylint: disable=broad-exception-caught
                        result = f"[发送失败] {error}"
                    on_target_replied(target_agent.name, result)

                target_agents = [
                    agent for agent in self._agents.values()
                    if agent.name in targets
                ]
                await asyncio.gather(
                    *(dispatch_target_reply(agent) for agent in target_agents)
                )
                Studio._print_speech(from_name, await from_agent.send())

            if any(agent.name in targets for agent in self._agents.values()):
                task = asyncio.create_task(dispatch_speak_round())
                self._pending_speak_tasks.add(task)
                task.add_done_callback(self._pending_speak_tasks.discard)
            return "message sent."

        return speak_tool

    async def send(self, message: str) -> str:
        """向主程发送用户消息，等待本轮群聊结束并返回其回复。"""
        self._ethan.add_message("user", f"用户:\n{message}")
        ethan_reply = await self._ethan.send()
        if ethan_reply:
            Studio._print_speech("ethan", ethan_reply)
        while self._pending_speak_tasks:
            await asyncio.gather(*self._pending_speak_tasks)
        return ethan_reply
