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
        success, message = await self.__coding()
        if success:
            #review
            return message
        else:
            return message
    
    async def __coding(self) -> tuple[bool, str]:
        """根据描述执行开发工作并返回简报。"""
        for _ in range(5):
            self.__developer.add_message(
                "user",
                f"需求文件在 {self.task_path}，请读取后开始开发。注意：你无权编辑该需求文件。"
                "如果开发完成，请输出三个尖括号包裹的`完成`并输出简报，例如`<<<完成>>>\n简报`\n"
                "如果你认为开发工作无法完成，或者需求不够明确，请输出三个尖括号包裹的`打回`并输出简报，例如`<<<打回>>>\n简报`\n"
            )
            finish_marker = "<<<完成>>>"
            reject_marker = "<<<打回>>>"
            result = (await self.__developer.send()).strip()
            if result.startswith(finish_marker):
                return True, f'"{self.title}"开发工作完成,简报如下:\n{result[len(finish_marker):].strip()}\n\n'
            if result.startswith(reject_marker):
                return False, (
                    f'"{self.title}"开发工作被打回,理由如下:\n{result[len(reject_marker):].strip()}\n\n'
                    "请考虑调整任务描述重新委派工作，或者和用户沟通需求"
                )
        return False, f'"{self.title}"开发工作因为无法预测的错误而失败了'

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
