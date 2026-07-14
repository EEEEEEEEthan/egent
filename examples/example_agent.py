"""egent 聊天 CLI 示例。

运行前请在**当前工作目录**配置 ``.egent/.model.toml``::

    python examples/example_agent.py
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import _bootstrap  # noqa: F401  # pylint: disable=unused-import  # 必须在 import egent 之前

import conversation_printer
import egent.agent
import egent.builtin_tools.path_validator

_WORKING_DIRECTORY = Path.cwd().resolve().as_posix()
_DISCOVERABLE_RULE = egent.builtin_tools.path_validator.PathPermissionRule(
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
        f"{_WORKING_DIRECTORY}/.egent/.model.toml",
        f"{_WORKING_DIRECTORY}/.egent/.temp/task-*",
    ),
)


class Studio:
    """工作室，管理主程 agent 和开发工作委派。"""

    def __init__(self) -> None:
        self.leader: egent.agent.Agent

    async def _delegate_development_work(self, title: str, description: str) -> str:
        """委派开发工作
        @title: 开发工作标题,几个单词即可
        @description: 开发工作描述,务必精准且简练
        """
        developer_name = "Leo"
        print("委派开发工作")
        
        # 将任务描述写入临时文件
        task_dir = Path(".egent/.temp")
        task_dir.mkdir(parents=True, exist_ok=True)
        task_id = uuid.uuid4().hex[:8]
        task_file = task_dir / f"task-{task_id}.txt"
        task_file.write_text(description, encoding="utf-8")
        task_path = task_file.as_posix()
        
        developer = egent.agent.Agent(
            name=developer_name,
            settings="gpt5",
            system_prompt="你是开发工程师，负责根据描述开发代码",
            tools=(),
        )
        developer.path_permissions = egent.builtin_tools.path_validator.PathPermissions(
            discoverable=_DISCOVERABLE_RULE,
            readable=_READABLE_RULE,
            editable=_EDITABLE_RULE,
        )
        developer.add_message(
            "user",
            f"需求文件在 {task_path}，请读取后开始开发。注意：你无权编辑该需求文件。",
        )
        reminder = (
            "如果开发完成，请输出三个尖括号包裹的`完成`并输出简报，例如`<<<完成>>>\n简报`\n"
            "如果你认为开发工作无法完成，或者需求不够明确，请输出三个尖括号包裹的`打回`并输出简报，例如`<<<打回>>>\n简报`\n"
        )
        result = ""
        for _ in range(5):
            developer.add_message("user", reminder)
            result = (await developer.send()).strip()
            finish_marker = "<<<完成>>>"
            reject_marker = "<<<打回>>>"    
            if result.startswith(finish_marker):
                result = f'"{title}"开发工作完成,简报如下:\n{result[len(finish_marker):].strip()}\n\n'
                break
            if result.startswith(reject_marker):
                result = (
                    f'"{title}"开发工作被打回,理由如下:\n{result[len(reject_marker):].strip()}\n\n'
                    "请考虑调整任务描述重新委派工作，或者和用户沟通需求"
                )
                break
        else:
            result = f'"{title}"开发工作因为无法预测的错误而失败了'
        print(result)
        return result

    async def run(self) -> int:
        """运行交互式聊天，返回进程退出码。"""
        self.leader = egent.agent.Agent(
            name="ethan",
            settings="gpt5",
            system_prompt=(
                "你是ethan，你是这个项目的主程\n"
                "用户是资深程序员，也是制作人，沟通时不需要解释太多\n"
            ),
            tools=(self._delegate_development_work,),
        )
        self.leader.path_permissions = egent.builtin_tools.path_validator.PathPermissions(
            discoverable=_DISCOVERABLE_RULE,
            readable=_READABLE_RULE,
            editable=_NO_EDITABLE_RULE,
        )
        conversation_printer.ConversationPrinter(self.leader)
        while True:
            try:
                user_input = input(">>> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not user_input:
                continue
            self.leader.add_message("user", user_input)
            await self.leader.send()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(Studio().run()))
