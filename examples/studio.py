"""多 Agent 工作室：成员间 speak 工具与异步回合调度。"""

from __future__ import annotations

import asyncio

import _bootstrap  # noqa: F401  # pylint: disable=unused-import

import egent.agent
import egent.tool

_RESET = "\033[0m"
_RED = "\033[31m"
_WHITE = "\033[37m"


def print_speech(speaker: str, body: str) -> None:
    """打印角色发言。"""
    print(f"{_RED}{speaker}{_RESET}:\n{_WHITE}{body}{_RESET}")


class Studio:
    """同一对话空间内的 Agent 集合；成员通过 speak 工具互相对话。"""

    def __init__(self) -> None:
        self._agents: dict[str, egent.agent.Agent] = {}
        self._pending_speak_tasks: set[asyncio.Task[None]] = set()

    @property
    def agents(self) -> dict[str, egent.agent.Agent]:
        """成员表。"""
        return self._agents

    def add(self, agent: egent.agent.Agent) -> None:
        """注册成员。"""
        self._agents[agent.name] = agent

    def get_speak_tool(self, from_name: str) -> egent.tool.ToolCallable:
        """生成指定成员的 speak 工具。"""
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
            print_speech(f"{from_name}->{target_label}", prompt)
            for agent in self._agents.values():
                if agent.name in targets:
                    agent.add_message("user", f"{from_name}对你说:\n{prompt}")
                elif agent.name != from_name:
                    agent.add_message("user", f"{from_name}对{target_label}说:\n{prompt}")

            def on_target_replied(name: str, result: str) -> None:
                print_speech(f"{name}->{from_name}", result)
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
                print_speech(from_name, await from_agent.send())

            if any(agent.name in targets for agent in self._agents.values()):
                task = asyncio.create_task(dispatch_speak_round())
                self._pending_speak_tasks.add(task)
                task.add_done_callback(self._pending_speak_tasks.discard)
            return "message sent."

        return speak_tool

    async def await_idle(self) -> None:
        """等待所有 speak 异步回合结束。"""
        while self._pending_speak_tasks:
            await asyncio.gather(*self._pending_speak_tasks)
