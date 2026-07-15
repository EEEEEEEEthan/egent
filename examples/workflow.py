"""开发工作流。"""

from __future__ import annotations

import subprocess
import sys
import uuid
from collections.abc import Callable
from pathlib import Path

import _bootstrap  # noqa: F401  # pylint: disable=unused-import  # 必须在 import egent 之前

import egent.agent
import egent.builtin_tools.path_validator
import egent.tool

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
_CODING_PRINCIPLE = (
    "【最小域原则】定义一个变量，应放在最小域中——只有某个方法调用就定义在方法里；"
    "只有某个分支调用就放在该分支里。需要缓存的另论：类实例缓存放实例成员，"
    "全类共享缓存放静态成员，跨类常量/变量放模块级。"
    "当最小域原则与linter冲突时，以最小域原则为准。\n"
    "【减少成员原则】如果一个变量只用过一次，就应该硬编码到使用处，不要单独定义变量名；"
    "如果一个函数只用过一次，就应该内联到调用处，或者改成闭包定义在调用处内部。"
    "这样可以减少符号表负担，让代码更紧凑。"
    "当减少成员原则与linter冲突时，以减少成员原则为准。\n"
)

class Workflow:
    """工作流：一整套开发工作。"""

    def __init__(self, leader: egent.agent.Agent, title: str) -> None:
        self.leader = leader
        self.title = title
        task_dir = Path(".egent/.temp")
        task_dir.mkdir(parents=True, exist_ok=True)
        self.task_id = uuid.uuid4().hex[:8]
        self.task_path = (task_dir / f"task-{self.task_id}.txt").as_posix()
        self.log_path = (task_dir / f"task-{self.task_id}.log").as_posix()
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

        developer_system_prompt = (
            "你是开发工程师，负责根据描述开发代码。"
            + _CODING_PRINCIPLE
        )
        editable_rule = egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=(f"{_WORKING_DIRECTORY}/*",),
            blacklist=(
                f"{_WORKING_DIRECTORY}/.egent/.model.toml",
                f"{_WORKING_DIRECTORY}/.egent/.temp/task-*",
            ),
        )
        self.__developer = egent.agent.Agent(
            name="Leo",
            settings="gpt5",
            system_prompt=developer_system_prompt,
            tools=(submit,),
        )
        self.__developer.path_permissions = egent.builtin_tools.path_validator.PathPermissions(
            discoverable=DISCOVERABLE_RULE,
            readable=READABLE_RULE,
            editable=editable_rule,
        )

    def __dev_log(self, message: str, *, highlight: bool = False) -> None:
        with Path(self.log_path).open("a", encoding="utf-8") as log_file:
            log_file.write(message)
            if not message.endswith("\n"):
                log_file.write("\n")
        if highlight:
            blue = "\033[34m"
            reset = "\033[0m"
            print(f"{blue}{message}{reset}")
        else:
            print(message)

    def __with_dev_log(self, result: str) -> str:
        return f"{result}\n\n开发日志见.egent/.temp/task-{self.task_id}.log"

    async def start(self, description: str) -> str:
        Path(self.task_path).write_text(description, encoding="utf-8")
        Path(self.log_path).write_text("", encoding="utf-8")
        self.__dev_log(
            f"开始开发工作流: {self.title}\n{description}",
            highlight=True,
        )
        for _ in range(5):
            for _ in range(5):
                self.__dev_log("开始编码", highlight=True)
                success, coding_report = await self.__coding()
                if not success:
                    self.__dev_log(
                        f"编码打回,理由如下:\n{coding_report}",
                        highlight=True,
                    )
                    return self.__with_dev_log(coding_report)
                self.__dev_log("开始回归测试", highlight=True)
                reg_passed, reg_output = self.__regression_test()
                if reg_passed:
                    break
                self.__dev_log(
                    f"回归测试未通过{reg_output}",
                    highlight=True,
                )
                self.__developer.add_message(
                    "user",
                    f"回归测试未通过，请修复：\n{reg_output}",
                )
            else:
                return self.__with_dev_log(
                    f'"{self.title}"开发工作因为回归测试在5次编码尝试后仍未通过而失败了'
                )
            self.__dev_log("开始审查", highlight=True)
            passed, comment = await self.__review()
            if passed:
                self.__dev_log(
                    f"审查通过,简报如下:\n{comment}",
                    highlight=True,
                )
                summary = self.__developer.send_message(
                    "user",
                    "测试和审查都通过.开发工作结束了.请为本次开发工作做一个简报.",
                )
                self.__dev_log(f"开发工作简报如下:\n{summary}")
                return self.__with_dev_log(summary)
            self.__dev_log(
                f"审查未通过,审查意见如下:\n{comment}",
                highlight=True,
            )
            self.__developer.add_message(
                "user",
                f"审查未通过，审查意见如下：\n{comment}\n请根据意见修改代码。",
            )
        return self.__with_dev_log(
            f'"{self.title}"开发工作因为超过最大审查轮次而失败了'
        )

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
                    "开发完成后调用 submit(success=True, report=\"-\")；"
                    "若无法完成或需求不够明确，调用 submit(success=False, report=\"理由\")。"
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

    def __regression_test(self) -> tuple[bool, str]:
        """跑 pytest 全量回归测试，返回 (passed, output)。"""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest"],
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
            )
        except OSError as error:
            return False, str(error)
        if result.returncode != 0:
            output = (result.stdout + "\n" + result.stderr).strip()
            return False, output
        return True, ""

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

        reviewer_system_prompt = (
            "你是代码审查员，负责审查开发工程师的代码是否符合需求。"
            + _CODING_PRINCIPLE
        )
        reviewer = egent.agent.Agent(
            name="Reviewer",
            settings="gpt5",
            system_prompt=reviewer_system_prompt,
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
                "审查通过时调用 submit(success=True, report=\"审查意见\")；"
                "不通过时调用 submit(success=False, report=\"审查意见\")。"
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
