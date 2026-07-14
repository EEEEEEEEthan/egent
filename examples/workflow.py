"""开发工作流。"""

from __future__ import annotations

import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path

import _bootstrap  # noqa: F401  # pylint: disable=unused-import  # 必须在 import egent 之前

import egent.agent
import egent.builtin_tools.path_validator
import egent.tool

BLUE = "\033[34m"
RESET = "\033[0m"

_WORKING_DIRECTORY = Path.cwd().resolve().as_posix()
DISCOVERABLE_RULE = egent.builtin_tools.path_validator.PathPermissionRule(
    whitelist=("*",),
    blacklist=(
        f"{_WORKING_DIRECTORY}/.git",
        f"{_WORKING_DIRECTORY}/.git/*",
        f"{_WORKING_DIRECTORY}/**/__pycache__",
        f"{_WORKING_DIRECTORY}/**/__pycache__/*",
        f"{_WORKING_DIRECTORY}/**/.pytest_cache",
        f"{_WORKING_DIRECTORY}/**/.pytest_cache/*",
        f"{_WORKING_DIRECTORY}/**/.ruff_cache",
        f"{_WORKING_DIRECTORY}/**/.ruff_cache/*",
    ),
)
READABLE_RULE = egent.builtin_tools.path_validator.PathPermissionRule(
    whitelist=("*",),
    blacklist=(f"{_WORKING_DIRECTORY}/.egent/.model.toml",),
)
NO_EDITABLE_RULE = egent.builtin_tools.path_validator.PathPermissionRule(
    whitelist=(),
    blacklist=("*",),
)
EDITABLE_RULE = egent.builtin_tools.path_validator.PathPermissionRule(
    whitelist=(f"{_WORKING_DIRECTORY}/*",),
    blacklist=(
        f"{_WORKING_DIRECTORY}/.egent/.model.toml",
        f"{_WORKING_DIRECTORY}/.egent/.temp/task-*",
    ),
)

_DEVELOPER_SYSTEM_PROMPT = "你是开发工程师，负责根据描述开发代码"
_REVIEWER_SYSTEM_PROMPT = "你是代码审查员，负责审查开发工程师的代码是否符合需求。"


class Workflow:
    """工作流：一整套开发工作。"""

    def __init__(self, leader: egent.agent.Agent, title: str) -> None:
        self.leader = leader
        self.title = title
        task_dir = Path(".egent/.temp")
        task_dir.mkdir(parents=True, exist_ok=True)
        task_id = uuid.uuid4().hex[:8]
        task_file = task_dir / f"task-{task_id}.txt"
        self.task_path = task_file.as_posix()
        self.__coding_submit_hook: Callable[[bool, str], None] | None = None

        @egent.tool.end_conversation
        def submit(success: bool, report: str) -> str:
            """提交开发结论并结束本轮对话。
            @param success: True 表示开发完成，False 表示打回（无法完成或需求不明）
            @param report: 完成简报，或打回理由
            """
            if self.__coding_submit_hook is None:
                raise RuntimeError("当前不在编码流程中，不能调用 submit")
            self.__coding_submit_hook(success, report)
            return "已提交"

        self.__developer = egent.agent.Agent(
            name="Leo",
            settings="gpt5",
            system_prompt=_DEVELOPER_SYSTEM_PROMPT,
            tools=(submit,),
        )
        self.__developer.path_permissions = egent.builtin_tools.path_validator.PathPermissions(
            discoverable=DISCOVERABLE_RULE,
            readable=READABLE_RULE,
            editable=EDITABLE_RULE,
        )

    async def start(self, description: str) -> str:
        Path(self.task_path).write_text(description, encoding="utf-8")
        print(f"{BLUE}开始开发工作流{RESET}: {self.title}\n{description}")
        for _ in range(5):
            print(f"{BLUE}开始编码{RESET}")
            success, message = await self.__coding()
            if not success:
                print(f"{BLUE}编码打回{RESET},理由如下:\n{message}")
                return message
            print(f"{BLUE}开始审查{RESET}")
            passed, comment = await self.__review()
            if passed:
                print(f"{BLUE}审查通过{RESET},简报如下:\n{message}")
                return message
            print(f"{BLUE}审查未通过{RESET},审查意见如下:\n{comment}")
            self.__developer.add_message(
                "user",
                f"审查未通过，审查意见如下：\n{comment}\n请根据意见修改代码。",
            )
        return f'"{self.title}"开发工作因为超过最大审查轮次而失败了'

    async def __coding(self) -> tuple[bool, str]:
        """根据描述执行开发工作并返回简报。"""
        submit_result: tuple[bool, str] | None = None

        def on_submit(success: bool, report: str) -> None:
            nonlocal submit_result
            submit_result = (success, report)

        self.__coding_submit_hook = on_submit
        try:
            for _ in range(5):
                submit_result = None
                self.__developer.add_message(
                    "user",
                    f"需求文件在 {self.task_path}，请读取后开始开发。注意：你无权编辑该需求文件。"
                    "开发完成后调用 submit(success=True, report=简报)；"
                    "若无法完成或需求不够明确，调用 submit(success=False, report=理由)。"
                    "必须通过 submit 提交结论。",
                )
                await self.__developer.send()
                if submit_result is not None:
                    success, report = submit_result
                    if success:
                        return True, f'"{self.title}"开发工作完成,简报如下:\n{report}\n\n'
                    return False, (
                        f'"{self.title}"开发工作被打回,理由如下:\n{report}\n\n'
                        "请考虑调整任务描述重新委派工作，或者和用户沟通需求"
                    )
            return False, f'"{self.title}"开发工作因为无法预测的错误而失败了: 未调用 submit'
        finally:
            self.__coding_submit_hook = None

    async def __review(self) -> tuple[bool, str]:
        """审查开发成果，返回 (passed, comment)。"""
        submit_result: tuple[bool, str] | None = None

        @egent.tool.end_conversation
        def submit(success: bool, report: str) -> str:
            """提交审查结论并结束本轮对话。
            @param success: True 表示审查通过，False 表示不通过
            @param report: 通过说明，或不通过时的具体修改意见
            """
            nonlocal submit_result
            submit_result = (success, report)
            return "已提交"

        def git_diff(staged: bool = False, cached: bool = False) -> str:
            """查看代码变更 diff。
            @param staged: True 查看已暂存到 index 的变更（git diff --staged）
            @param cached: True 查看工作区相对 HEAD 的全部变更（git diff HEAD）。与 staged 互斥，cached 优先。
            """
            args = ["git", "diff"]
            if cached:
                args.append("HEAD")
            elif staged:
                args.append("--staged")
            result = subprocess.run(args, capture_output=True, text=True, cwd=Path.cwd())
            output = result.stdout.strip()
            if not output:
                return "没有 diff（工作区干净，或没有可展示的变更）"
            return output

        reviewer = egent.agent.Agent(
            name="Reviewer",
            settings="gpt5",
            system_prompt=_REVIEWER_SYSTEM_PROMPT,
            tools=(submit, git_diff),
        )
        reviewer.path_permissions = egent.builtin_tools.path_validator.PathPermissions(
            discoverable=DISCOVERABLE_RULE,
            readable=READABLE_RULE,
            editable=NO_EDITABLE_RULE,
        )
        for _ in range(5):
            submit_result = None
            reviewer.add_message(
                "user",
                f"需求文件在 {self.task_path}，请审查代码是否符合需求。"
                "审查通过时调用 submit(success=True, report=简要说明)；"
                "不通过时调用 submit(success=False, report=具体意见)。"
                "必须通过 submit 提交结论。",
            )
            await reviewer.send()
            if submit_result is not None:
                return submit_result
        return False, f'"{self.title}"审查工作因为无法预测的错误而失败了: 未调用 submit'


async def begin_work_flow(
    leader: egent.agent.Agent,
    title: str,
    description: str,
) -> str:
    """启动工作流
    @param title: 工作流标题,几个单词即可
    @param description: 工作流描述,务必精准且简练
    """
    return await Workflow(leader, title).start(description)
