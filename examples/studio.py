"""多 Agent 工作室：成员间 speak 工具与异步回合调度。"""
from __future__ import annotations
import asyncio
from pathlib import Path
import _bootstrap  # noqa: F401  # pylint: disable=unused-import
import work_order
import egent.agent
import egent.builtin_tools.path_validator
import egent.tool

_WORKFLOW_DONE_MARKER = "<<<完成>>>"
_WORKFLOW_ABORT_MARKER = "<<<放弃>>>"


def _coding_workflow_switcher(
    result: str,
) -> tuple[work_order.WorkOrderNode | None, work_order.HandoffMessage]:
    if result.startswith(_WORKFLOW_DONE_MARKER) or result.startswith(_WORKFLOW_ABORT_MARKER):
        return None, result
    return None, None


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
        general_system_prompt = (
            "你不必复述群聊内容"
        )
        self.__agents["Ethan"] = egent.agent.Agent(
            name="Ethan",
            settings="gpt5",
            system_prompt=
                "你是Ethan,你是这个项目的主程\n"
                "Milo是你的助理,Leo是开发工程师负责写代码\n"
                "如果需要看代码,尽量和Milo说让他先看,帮你筛选出关键代码,然后你再去看.尽量不要直接看,这会耽误你太多时间\n"
                f"如果需要开发,在做好分析和设计之后,用{self.__begin_develop_workflow.__name__}发起开发工作流\n"
                f"{general_system_prompt}\n"
                "用户是资深程序员,也是制作人,所以你和用户沟通的时候不需要解释太多.但是你需要挖掘用户的真实需求\n"
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
                f"{general_system_prompt}\n"
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
                f"{general_system_prompt}\n"
                "用户是资深程序员,沟通时不需要解释太多\n"
            ,
            skills=(),
            tools=(
                self.__get_speak_tool("Leo"),
                self.__begin_develop_workflow
            ),
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
        ethan_reply = await self.__agents["Ethan"].send_message("user", f"用户:\n{message}")
        if ethan_reply:
            Studio.__print_speech("Ethan", ethan_reply)
        while self.__pending_speak_tasks:
            await asyncio.gather(*self.__pending_speak_tasks)
        return ethan_reply

    async def __begin_develop_workflow(self, prompt: str) -> str:
        """开始开发工作流.
        @param prompt: 开发需求.请务必精准,措辞简练
        @return: 开发工作流结果
        """
        def coding_switcher(
            result: str,
        ) -> tuple[work_order.WorkOrderNode | None, work_order.HandoffMessage]:
            if result.startswith("<<<完成>>>") or result.startswith("<<<放弃>>>"):
                return None, result
            return None, None
        node_coding = work_order.WorkOrderNode(
            agent=self.__agents["Ethan"],
            submit_notification=(
                "工作完毕后回复三个尖括号包裹的`完成`或者`放弃`,"
                "并说明理由,例如`<<<放弃>>>我没有权限编辑`"
            ),
            switcher=coding_switcher,
        )
        return await node_coding.begin(prompt, "")

    @staticmethod
    def __print_speech(speaker: str, body: str) -> None:
        print(f"\033[31m{speaker}\033[0m:\n\033[37m{body}\033[0m")

    def __get_speak_tool(self, from_name: str) -> egent.tool.ToolCallable:
        @egent.tool.end_conversation
        async def speak_tool(to_names: list[str], prompt: str) -> str:
            """和指定角色说话.他或者他们会回复你.但是你不能通过这个工具委派编辑工作.编辑工作需要走正式的编辑流程.
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
            target_prompts = {
                agent.name: f"[群聊]{from_name}对你说:\n{prompt}"
                for agent in self.__agents.values()
                if agent.name in targets
            }
            for agent in self.__agents.values():
                if agent.name not in targets and agent.name != from_name:
                    agent.add_message("user", f"[群聊]{from_name}对{target_label}说:\n{prompt}")
            async def dispatch_speak_round() -> None:
                async def dispatch_target_reply(target_agent: egent.agent.Agent) -> None:
                    permissions = target_agent.path_permissions
                    try:
                        result = await target_agent.send_message(
                            "user",
                            target_prompts[target_agent.name],
                        )
                    except Exception as error:  # pylint: disable=broad-exception-caught
                        result = f"[发送失败] {error}"
                    finally:
                        target_agent.path_permissions = permissions
                    Studio.__print_speech(f"{target_agent.name}->{from_name}", result)
                    from_agent.add_message("user", f"[群聊]{target_agent.name}回复:\n{result}")
                    for agent in self.__agents.values():
                        if agent.name not in targets and agent.name != from_name:
                            agent.add_message(
                                "user",
                                f"[群聊]{target_agent.name}回复{from_name}:\n{result}",
                            )
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
