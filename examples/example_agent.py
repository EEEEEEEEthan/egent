"""egent 聊天 CLI 示例。

运行前请在**当前工作目录**配置 ``.egent/.model.toml``::

    python examples/example_agent.py
"""

from __future__ import annotations

import asyncio
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
    ),
)


async def async_main() -> int:
    """运行交互式聊天，返回进程退出码。"""
    leader: egent.agent.Agent
    @egent.tool.end_conversation
    def _delegate_development_work(description: str) -> str:
        """委派开发工作
        @description: 开发工作描述，务必精准且简练
        """
        developer_name = "Leo"
        print("委派开发工作")
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
        developer.add_message("user", description)
        reminder = (
            "如果开发完成，请输出三个尖括号包裹的`完成`并输出简报，例如`<<<完成>>>\n简报`\n"
            "如果你认为开发工作无法完成，或者需求不够明确，请输出三个尖括号包裹的`打回`并输出简报，例如`<<<打回>>>\n简报`\n"
        )
        async def send():
            for _ in range(5):
                developer.add_message("user", reminder)
                result = (await developer.send()).strip()
                if result.startswith("<<<完成>>>"):
                    return result[len("<<<完成>>>"):]
                if result.startswith("<<<打回>>>"):
                    return(
                        f"开发工作被打回,理由如下:\n{result[len("<<<打回>>>"):].strip()}\n\n"
                        "请考虑调整任务描述重新委派工作，或者和用户沟通需求"
                )
            return "开发工作因为无法预测的错误而失败了"
        send()
        return f"已委派开发工作给{developer_name}"

    leader = egent.agent.Agent(
        name="ethan",
        settings="gpt5",
        system_prompt=(
            "你是ethan，你是这个项目的主程\n"
            "用户是资深程序员，也是制作人，沟通时不需要解释太多\n"
        ),
        tools=(_delegate_development_work,),
    )
    leader.path_permissions = egent.builtin_tools.path_validator.PathPermissions(
        discoverable=_DISCOVERABLE_RULE,
        readable=_READABLE_RULE,
        editable=_NO_EDITABLE_RULE,
    )
    conversation_printer.ConversationPrinter(leader)
    while True:
        try:
            user_input = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not user_input:
            continue
        leader.add_message("user", user_input)
        await leader.send()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
