"""egent 聊天 CLI 示例。

运行前请在**当前工作目录**配置 ``.egent/.model.toml``::

    python examples/example_agent.py
"""

from __future__ import annotations

import asyncio

import _bootstrap  # noqa: F401  # pylint: disable=unused-import  # 必须在 import egent 之前

import conversation_printer
import egent.agent
import egent.builtin_tools.path_validator
import workflow


async def run() -> int:
    """运行交互式聊天，返回进程退出码。"""

    async def begin_work_flow(title: str, description: str) -> str:
        """启动工作流
        @param title: 工作流标题,几个单词即可
        @param description: 工作流描述,务必精准
        """
        nonlocal leader
        return await workflow.begin_work_flow(leader, title, description)

    leader = egent.agent.Agent(
        name="ethan",
        settings="gpt5",
        system_prompt=(
            "你是ethan，你是这个项目的主程\n"
            "用户是资深程序员，也是制作人，沟通时不需要解释太多\n"
            f"开发工作(修改项目)请使用{begin_work_flow.__name__},而不要亲自执行"
        ),
        tools=(begin_work_flow,),
    )
    leader.path_permissions = egent.builtin_tools.path_validator.PathPermissions(
        discoverable=workflow.DISCOVERABLE_RULE,
        readable=workflow.READABLE_RULE,
        editable=workflow.NO_EDITABLE_RULE,
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
    raise SystemExit(asyncio.run(run()))
