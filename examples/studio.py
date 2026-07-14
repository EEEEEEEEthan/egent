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

    def __init__(self) -> None:
        self.__agents: dict[str, egent.agent.Agent] = {}
        self.__pending_speak_tasks: set[asyncio.Task[None]] = set[asyncio.Task[None]]()
        self.__agents["Ethan"] = egent.agent.Agent(
            name="Ethan",
            settings="gpt5",
            system_prompt=
                "你是Ethan,你是这个项目的主程\n"
                "Milo是你的助理,Leo是开发工程师负责写代码\n"
                "如果需要看代码,尽量和Milo说让他先看,帮你筛选出关键代码,然后你再去看.尽量不要直接看,这会耽误你太多时间\n"
                "如果需要改代码,让Leo去做\n"
                "这是群聊,所以你不必把别人的话复述给用户\n"
                "用户是资深程序员,也是制作人,所以你和用户沟通的时候不需要解释太多\n"
            ,
            skills=(),
            tools=(self.__get_speak_tool("Ethan"),),
        )
        self.__agents["Ethan"].path_permissions = (
            egent.builtin_tools.path_validator.PathPermissions(
                discoverable=Studio._DISCOVERABLE_RULE,
                readable=Studio._READABLE_RULE,
                editable=Studio._NO_EDITABLE_RULE,
            )
        )
        self.__agents["Milo"] = egent.agent.Agent(
            name="Milo",
            settings="gpt5",
            system_prompt=
                "你是Milo,是Ethan的助理。Ethan是这个项目的主程\n"
            ,
            skills=(),
            tools=(self.__get_speak_tool("Milo"),),
        )
        self.__agents["Milo"].path_permissions = (
            egent.builtin_tools.path_validator.PathPermissions(
                discoverable=Studio._DISCOVERABLE_RULE,
                readable=Studio._READABLE_RULE,
                editable=Studio._NO_EDITABLE_RULE,
            )
        )
        self.__agents["Leo"] = egent.agent.Agent(
            name="Leo",
            settings="gpt5",
            system_prompt=
                "你是Leo,开发工程师,负责编写和修改代码\n"
                "Ethan是主程,Milo负责帮Ethan读代码\n"
                "收到写代码任务后,先了解上下文再动手,改完简要说明改了什么\n"
                "这是群聊,所以你不必把别人的话复述给用户\n"
                "用户是资深程序员,沟通时不需要解释太多\n"
            ,
            skills=(),
            tools=(self.__get_speak_tool("Leo"),),
        )
        self.__agents["Leo"].path_permissions = (
            egent.builtin_tools.path_validator.PathPermissions(
                discoverable=Studio._DISCOVERABLE_RULE,
                readable=Studio._READABLE_RULE,
                editable=Studio._EDITABLE_RULE,
            )
        )

    async def send(self, message: str) -> str:
        """向主程发送用户消息,等待本轮群聊结束并返回其回复。"""
        await self.__agents["Ethan"].await_free()
        self.__agents["Ethan"].add_message("user", f"用户:\n{message}")
        ethan_reply = await self.__agents["Ethan"].send()
        if ethan_reply:
            Studio.__print_speech("Ethan", ethan_reply)
        while self.__pending_speak_tasks:
            await asyncio.gather(*self.__pending_speak_tasks)
        return ethan_reply

    @staticmethod
    def __print_speech(speaker: str, body: str) -> None:
        print(f"\033[31m{speaker}\033[0m:\n\033[37m{body}\033[0m")

    def __get_speak_tool(self, from_name: str) -> egent.tool.ToolCallable:
        @egent.tool.end_conversation
        async def speak_tool(to_names: list[str], prompt: str) -> str:
            """对指定角色说话；回复通过回调异步送达,不阻塞本工具返回
            @param to_names: 说话对象（可多个）
            @param prompt: 说话内容
            @return: 发送确认
            """
            if from_name in to_names:
                raise ValueError(f"不能对自己说话：{from_name}")
            from_agent = self.__agents.get(from_name)
            targets = set[str](to_names)
            target_label = ", ".join(to_names)
            Studio.__print_speech(f"{from_name}->{target_label}", prompt)
            for agent in self.__agents.values():
                if agent.name in targets:
                    agent.add_message("user", f"{from_name}对你说:\n{prompt}")
                elif agent.name != from_name:
                    agent.add_message("user", f"{from_name}对{target_label}说:\n{prompt}")
            def on_target_replied(name: str, result: str) -> None:
                Studio.__print_speech(f"{name}->{from_name}", result)
                from_agent.add_message("user", f"{name}回复:\n{result}")
                for agent in self.__agents.values():
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
                    agent for agent in self.__agents.values()
                    if agent.name in targets
                ]
                await asyncio.gather(
                    *(dispatch_target_reply(agent) for agent in target_agents)
                )
                Studio.__print_speech(from_name, await from_agent.send())
            if any(agent.name in targets for agent in self.__agents.values()):
                task = asyncio.create_task(dispatch_speak_round())
                self.__pending_speak_tasks.add(task)
                task.add_done_callback(self.__pending_speak_tasks.discard)
            return "message sent."
        return speak_tool
