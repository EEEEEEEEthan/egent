"""开发工作流。"""

from __future__ import annotations

import uuid
from pathlib import Path

import _bootstrap  # noqa: F401  # pylint: disable=unused-import  # 必须在 import egent 之前

import egent.agent
import egent.builtin_tools.path_validator

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
        developer_name = "Leo"
        self.__developer = egent.agent.Agent(
            name=developer_name,
            settings="gpt5",
            system_prompt="你是开发工程师，负责根据描述开发代码",
            tools=(),
        )
        self.__developer.path_permissions = egent.builtin_tools.path_validator.PathPermissions(
            discoverable=DISCOVERABLE_RULE,
            readable=READABLE_RULE,
            editable=EDITABLE_RULE,
        )

    async def start(self, description: str) -> str:
        Path(self.task_path).write_text(description, encoding="utf-8")
        print(f"开始开发工作流: {self.title}\n{description}")
        for _ in range(5):
            print("开始编码")
            success, message = await self.__coding()
            if not success:
                print(f"编码打回,理由如下:\n{message}")
                return message
            print("开始审查")
            passed, comment = await self.__review()
            if passed:
                print(f"审查通过,简报如下:\n{message}")
                return message
            print(f"审查未通过,审查意见如下:\n{comment}")
            self.__developer.add_message(
                "user",
                f"审查未通过，审查意见如下：\n{comment}\n请根据意见修改代码。",
            )
        return f'"{self.title}"开发工作因为超过最大审查轮次而失败了'

    async def __coding(self) -> tuple[bool, str]:
        """根据描述执行开发工作并返回简报。"""
        for _ in range(5):
            finish_marker = "<<<完成>>>"
            reject_marker = "<<<打回>>>"
            self.__developer.add_message(
                "user",
                f"需求文件在 {self.task_path}，请读取后开始开发。注意：你无权编辑该需求文件。"
                f"如果开发完成，请输出`{finish_marker}`并输出简报，例如`{finish_marker}\n简报`\n"
                f"如果你认为开发工作无法完成，或者需求不够明确，请输出`{reject_marker}`并输出简报，例如`{reject_marker}\n简报`\n"
            )
            result = (await self.__developer.send()).strip()
            if result.startswith(finish_marker):
                return True, f'"{self.title}"开发工作完成,简报如下:\n{result[len(finish_marker):].strip()}\n\n'
            if result.startswith(reject_marker):
                return False, (
                    f'"{self.title}"开发工作被打回,理由如下:\n{result[len(reject_marker):].strip()}\n\n'
                    "请考虑调整任务描述重新委派工作，或者和用户沟通需求"
                )
        return False, f'"{self.title}"开发工作因为无法预测的错误而失败了:\n{result}'

    async def __review(self) -> tuple[bool, str]:
        """审查开发成果，返回 (passed, comment)。"""
        pass_marker = "<<<通过>>>"
        fail_marker = "<<<打回>>>"
        reviewer = egent.agent.Agent(
            name="Reviewer",
            settings="gpt5",
            system_prompt="你是代码审查员，负责审查开发工程师的代码是否符合需求。",
            tools=(),
        )
        for _ in range(5):
            reviewer.path_permissions = egent.builtin_tools.path_validator.PathPermissions(
                discoverable=DISCOVERABLE_RULE,
                readable=READABLE_RULE,
                editable=NO_EDITABLE_RULE,
            )
            reviewer.add_message(
                "user",
                f"需求文件在 {self.task_path}，请审查代码是否符合需求。"
                f"如果审查通过，请输出`{pass_marker}`并输出简要说明，例如`{pass_marker}\n说明`\n"
                f"如果审查不通过，请输出三个尖括号包裹的`{fail_marker}`并输出具体意见，例如`{fail_marker}\n意见`\n"
            )
            result = (await reviewer.send()).strip()
            if result.startswith(pass_marker):
                return True, result[len(pass_marker):].strip()
            if result.startswith(fail_marker):
                return False, result[len(fail_marker):].strip()
        return False, f'"{self.title}"审查工作因为无法预测的错误而失败了:\n{result}'

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
