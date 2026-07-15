"""开发工作流。"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path

import _bootstrap  # noqa: F401  # pylint: disable=unused-import  # 必须在 import egent 之前

import shell_tools
import egent.agent
import egent.builtin_tools.path_validator
import egent.builtin_tools.test_tools
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
    "【最佳实现原则】实现应该尽可能优雅,不要过度设计和过度封装.也不要执着于最小修改."
    "如果重构可以带来更优雅的实现,应该优先考虑重构.\n"
)


def _discover_test_files() -> str:
    """扫描 tests/ 目录下所有 test_*.py 文件，返回顿号分隔的相对路径字符串。"""
    tests_dir = Path.cwd() / "tests"
    if not tests_dir.is_dir():
        return ""
    return "、".join(
        str(p.relative_to(Path.cwd())) for p in sorted(tests_dir.rglob("test_*.py"))
    )


class Workflow:  # pylint: disable=too-few-public-methods
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

        def run_regression_test(targets: str) -> str:  # pylint: disable=redefined-outer-name
            """placeholder"""
            return egent.builtin_tools.test_tools.run_regression_test(targets)

        run_regression_test.__doc__ = (
            "运行 pytest 回归测试，验证当前代码状态。\n"
            f"@param targets: 与本次开发相关的测试路径或节点（如 tests/test_foo.py::test_bar），"
            f"空格分隔；可用测试文件：{_discover_test_files()}"
        )

        @egent.tool.end_conversation
        def submit(success: bool, report: str) -> str:
            """提交开发结论并结束本轮对话。打回并不羞耻! 请大胆打回.
            应当打回的情况包括但不限于:回归测试无法通过不是我造成的;需求不够清晰;代码脏乱建议先重构;审查标准与需求冲突等等.
            @param success: True 表示开发完成，False 表示打回
            @param report: 如果完成,填写开发简报;如果打回,请说明理由
            """
            if self.__coding_submit_hook is None:
                raise RuntimeError("当前不在编码流程中，不能调用 submit")
            self.__coding_submit_hook(success, report)
            return "已提交"

        developer_system_prompt = (
            "你是开发工程师，负责根据描述开发代码。"
            "开发过程中可用 run_regression_test 验证与你本次改动相关的测试."
            "你需要跑的测试有pylint和你的修改对应的测试.提交后会自动进行全量回归测试。"
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
            tools=(submit, run_regression_test),
        )
        self.__developer.path_permissions = egent.builtin_tools.path_validator.PathPermissions(
            discoverable=DISCOVERABLE_RULE,
            readable=READABLE_RULE,
            editable=editable_rule,
        )

    def __dev_log(self, title: str, content: str = "") -> None:
        with Path(self.log_path).open("a", encoding="utf-8") as log_file:
            log_file.write(title)
            log_file.write("\n")
            if content:
                log_file.write(content)
                log_file.write("\n")
            log_file.write("\n")
        blue = "\033[34m"
        reset = "\033[0m"
        print(f"{blue}{title}{reset}")
        if content:
            print(content)

    async def start(self, description: str) -> str:
        """按描述启动开发工作流，返回最终报告。"""
        success, report = await self.__start(description)
        report = f"{report}\n\n开发日志见.egent/.temp/task-{self.task_id}.log"
        if not success:
            reset_ok, reset_output = reset_git_workspace()
            if reset_ok:
                self.__dev_log("工作流失败，已强制恢复 git 工作区", reset_output)
            else:
                self.__dev_log("工作流失败，git 恢复失败", reset_output)
                report += f"\n\ngit 恢复失败：\n{reset_output}"
            report += "\n\n请考虑调整需求描述重新委派开发工作或者与用户重新讨论需求."
        return report

    async def __start(self, description: str) -> tuple[bool, str]:
        Path(self.task_path).write_text(description, encoding="utf-8")
        Path(self.log_path).write_text("", encoding="utf-8")
        self.__dev_log(f"开始开发工作流: {self.title}", description)
        for _ in range(10):
            for _ in range(10):
                self.__dev_log("开始编码")
                success, coding_report = await self.__coding()
                if not success:
                    self.__dev_log("需求被打回,理由如下:", coding_report)
                    return False, coding_report
                self.__dev_log("编码完成,简报如下:", coding_report)
                self.__dev_log("开始回归测试")
                reg_passed, reg_output = run_regression_test()
                if reg_passed:
                    break
                self.__dev_log("回归测试未通过", reg_output)
                self.__developer.add_message(
                    "user",
                    f"回归测试未通过，请修复：\n{reg_output}",
                )
            else:
                return False, (
                    f'"{self.title}"开发工作因为回归测试在5次编码尝试后仍未通过而失败了'
                )
            self.__dev_log("开始审查")
            passed, comment = await self.__review()
            if passed:
                self.__dev_log("审查通过,简报如下:", comment)
                summary = await self.__developer.send_message(
                    "user",
                    "测试和审查都通过.开发工作结束了.请为本次开发工作做一个简报.",
                )
                self.__dev_log("开发工作简报如下:", summary)
                return True, summary
            self.__dev_log("审查未通过,审查意见如下:", comment)
            self.__developer.add_message(
                "user",
                f"审查未通过，审查意见如下：\n{comment}\n请根据意见修改代码。",
            )
        return False, f'"{self.title}"开发工作因为超过最大审查轮次而失败了'

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
                    "开发完成后调用 submit(success=True, report=\"开发简报\")；"
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

        def git_diff() -> str:
            """查看代码变更 diff。返回工作区相对 HEAD 的全部变更（git diff HEAD）。"""
            _, output = shell_tools.run_command("git", "diff", "HEAD")
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
                "必须通过 submit 提交结论。\n",
                "checklist:\n"
                "- 回归测试是否能覆盖到本次修改\n"
                "- 是否符合项目规范\n"
                "- 是否带来了不必要的修改\n"
                "- 有没有更优雅的实现\n"
            )
            await reviewer.send()
            if submit_result is not None:
                return submit_result
        return False, f'"{self.title}"审查工作因为无法预测的错误而失败了: 未调用 submit'


def reset_git_workspace() -> tuple[bool, str]:
    """将工作区强制恢复为 HEAD 干净状态，返回 (success, output)。"""
    reset_code, reset_output = shell_tools.run_command("git", "reset", "--hard", "HEAD")
    clean_code, clean_output = shell_tools.run_command("git", "clean", "-fd")
    output = "\n".join(part for part in (reset_output, clean_output) if part)
    if not output:
        output = "工作区已恢复为 HEAD 干净状态"
    if reset_code != 0 or clean_code != 0:
        return False, output
    return True, output


def run_regression_test() -> tuple[bool, str]:
    """跑 pytest 全量回归测试，返回 (passed, output)。"""
    passed, output = egent.builtin_tools.test_tools.execute_pytest(None)
    if passed:
        return True, ""
    return False, output


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
