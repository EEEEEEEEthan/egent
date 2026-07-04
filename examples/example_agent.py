"""egent 聊天 CLI 示例。

运行前请在**当前工作目录**配置 ``.egent/.model.toml``::

    pip install -e .
    python examples/example_agent.py
"""

from __future__ import annotations

from pathlib import Path

import example_workflow_develop
import example_workflow_todo
import _common
import conversation_printer
from egent import builtin_tools
from egent.conversation import Conversation

_EXAMPLE_GREET_SKILL = Path(__file__).resolve().parent.parent / ".agents" / "skills" / "example-greet"


async def run_turn(
    conversation: Conversation,
    printer: conversation_printer.ConversationPrinter,
) -> None:
    """运行一轮交互：收集用户输入并发送请求。

    每次 turn 重新构建工具列表、路径校验器和文件读取工具，
    使 ``reload_modules`` 后下一轮可以拿到更新后的工具函数。
    """
    path_validator = _common.EgentPathValidator()
    file_read_tools = builtin_tools.file_system_tools.get_read_tools(path_validator)
    conversation.add_message("user", input(">>> ").strip())
    await printer.request(tools=[
        *conversation.skill_tools,
        *file_read_tools,
        *builtin_tools.git_tools.read_only_tools,
        builtin_tools.git_tools.git_add,
        builtin_tools.git_tools.git_commit,
        _common.reload_modules,
        example_workflow_develop.delegate_develop_workflow,
        example_workflow_todo.todo_digest_workflow,
    ])


async def async_main() -> int:
    """运行交互式聊天，返回进程退出码。"""
    conversation = Conversation("gpt5", skills=[_EXAMPLE_GREET_SKILL])
    conversation.add_message(
        "system",
        """你时egent.你是这个agent项目的主管,同时,你就是这个项目驱动的agent.
        你接到的开发任务，你应该尽可能用workflow完成.

        # 批量任务
        对于todolist里的批量任务,可以使用todo_digest_workflow.

        # 单个任务
        对于单个工作可以使用delegate_develop_workflow. 如果这个任务可以拆成独立的多个任务,或者拆成连续的多个步骤,
        那么你就应该拆成多个任务或者多个步骤,依次交给你的手下,每做完一个任务提交一次.每做完一个提交一个.
        """,
    )
    printer = conversation_printer.ConversationPrinter(conversation)
    while True:
        await run_turn(conversation, printer)


if __name__ == "__main__":
    _common.run_cli(async_main)
