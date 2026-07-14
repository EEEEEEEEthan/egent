"""多 Agent 工作室：成员间私聊工具与异步回合调度。"""
from __future__ import annotations
import asyncio
import subprocess
from pathlib import Path
import _bootstrap  # noqa: F401  # pylint: disable=unused-import
import conversation_printer
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
    """同一对话空间内的 Agent 集合；成员通过私聊工具一对一对话。"""

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
        self.__pending_background_tasks: set[asyncio.Task[None]] = set[asyncio.Task[None]]()
        def get_introduce(name: str) -> str:
            def role_line(role: str, description: str) -> str:
                if name == role:
                    return f"你是{role},{description}"
                return f"{name}{description}"

            lines = [
                "你们在这个团队进行开发",
                role_line("Ethan", "是这个项目的主程"),
                role_line("Milo", "是这个项目的副主程,负责协助收集项目资料以及分析需求"),
                role_line("Leo", "是开发工程师负责写代码"),
            ]
            return "\n".join(lines) + "\n"
        self.__agents["Ethan"] = egent.agent.Agent(
            name="Ethan",
            settings="gpt5",
            system_prompt=
                f"{get_introduce("Ethan")}\n"
                "如果需要看代码,尽量和Milo说让他先看,帮你筛选出关键代码,然后你再去看.尽量不要直接看,这会耽误你太多时间\n"
                f"如果需要开发,在做好分析和设计之后,用{self.__begin_develop_workflow.__name__}发起开发工作流\n"
                "用户是资深程序员,也是制作人,所以你和用户沟通的时候不需要解释太多.但是你需要挖掘用户的真实需求\n"
            ,
            skills=(),
            tools=(
                self.__get_private_chat_tool("Ethan"),
                self.__begin_develop_workflow,
            ),
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
                f"{get_introduce("Milo")}\n"
            ,
            skills=(),
            tools=(self.__get_private_chat_tool("Milo"),),
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
                f"{get_introduce("Leo")}\n"
                "收到写代码任务后,先了解上下文再动手,改完简要说明改了什么\n"
                "用户是资深程序员,沟通时不需要解释太多\n"
            ,
            skills=(),
            tools=(self.__get_private_chat_tool("Leo"),),
        )
        self.__agents["Leo"].path_permissions = (
            egent.builtin_tools.path_validator.PathPermissions(
                discoverable=Studio._DISCOVERABLE_RULE,
                readable=Studio._READABLE_RULE,
                editable=Studio._EDITABLE_RULE,
            )
        )
        conversation_printer.ConversationPrinter(self.__agents["Ethan"])
        conversation_printer.ConversationPrinter(self.__agents["Milo"], 1)
        conversation_printer.ConversationPrinter(self.__agents["Leo"], 2)

    async def send(self, message: str) -> str:
        """向主程发送用户消息,等待本轮私聊结束并返回其回复。"""
        await self.await_free()
        ethan_reply = await self.__agents["Ethan"].send_message("user", f"用户:\n{message}")
        if ethan_reply:
            Studio.__print_speech("Ethan", ethan_reply)
        while self.__pending_background_tasks:
            await asyncio.gather(*self.__pending_background_tasks)
        return ethan_reply

    @egent.tool.end_conversation
    async def __begin_develop_workflow(self, prompt: str) -> str:
        """开始开发工作流.
        @param prompt: 开发需求.请务必精准,措辞简练
        @return: 开发工作流结果
        """
        def coding_switcher(
            result: str,
        ) -> tuple[work_order.WorkOrderNode | None, work_order.HandoffMessage]:
            if result.strip().startswith("<<<完成>>>") or result.strip().startswith("<<<放弃>>>"):
                return None, result
            return None, None

        def coding_validator(result: str) -> str | None:
            project_root = Path(__file__).resolve().parent.parent
            try:
                proc = subprocess.run(
                    ["pytest", "tests/", "-q", "--tb=short"],
                    cwd=project_root,
                    capture_output=True,
                    timeout=120,
                    text=True,
                )
            except subprocess.TimeoutExpired:
                return "回归测试超时 (120秒)"
            except FileNotFoundError:
                return "回归测试失败: 找不到 pytest 命令"
            except Exception as exc:  # pylint: disable=broad-exception-caught
                return f"回归测试异常: {exc}"
            if proc.returncode == 0:
                return None
            output = (proc.stdout + proc.stderr)[-2000:]
            return f"回归测试不通过 (exit code {proc.returncode}):\n{output}"

        node_coding = work_order.WorkOrderNode(
            agent=self.__agents["Leo"],
            submit_notification=(
                "工作完毕后回复:先用三个尖括号包裹的`完成`或者`放弃`,然后说明理由,例如`<<<放弃>>>我没有权限编辑`"
            ),
            switcher=coding_switcher,
            validator=coding_validator,
        )

        async def run_develop_workflow() -> None:
            ethan = self.__agents["Ethan"]
            try:
                result = await node_coding.begin(prompt, "")
            except Exception as error:  # pylint: disable=broad-exception-caught
                result = f"[工作流异常] {error}"
            await ethan.await_free()
            ethan.add_message("user", f"[开发工作流完成]\n{result}")
            follow_up = await ethan.send()
            if follow_up:
                Studio.__print_speech("Ethan", follow_up)

        task = asyncio.create_task(run_develop_workflow())
        self.__pending_background_tasks.add(task)
        task.add_done_callback(self.__pending_background_tasks.discard)
        return "开发工作流已启动，Leo 开发完成后会通知你。"

    async def await_free(self) -> None:
        """等待所有Agent空闲。"""
        for agent in self.__agents.values():
            await agent.await_free()

    @staticmethod
    def __print_speech(speaker: str, body: str) -> None:
        print(f"\033[31m{speaker}\033[0m:\n\033[37m{body}\033[0m")

    def __get_private_chat_tool(self, from_name: str) -> egent.tool.ToolCallable:
        async def private_chat_tool(to_name: str, prompt: str) -> str:
            """和指定角色私聊.对方会回复你.但是你不能通过这个工具委派编辑工作.编辑工作需要走正式的编辑流程.
            @param to_name: 私聊对象
            @param prompt: 消息内容
            @return: 对方回复
            """
            if from_name == to_name:
                raise ValueError(f"不能对自己说话：{from_name}")
            target_agent = self.__agents.get(to_name)
            if target_agent is None:
                raise ValueError(f"未知角色：{to_name}")
            Studio.__print_speech(f"{from_name}->{to_name}", prompt)
            permissions = target_agent.path_permissions
            try:
                target_agent.path_permissions = permissions.readonly_copy
                result = await target_agent.send_message(
                    "user",
                    f"[私聊]{from_name}对你说:\n{prompt}",
                )
            except Exception as error:  # pylint: disable=broad-exception-caught
                result = f"[发送失败] {error}"
            finally:
                target_agent.path_permissions = permissions
            Studio.__print_speech(f"{to_name}->{from_name}", result)
            return f"[私聊]{to_name}回复:\n{result}"
        return private_chat_tool
