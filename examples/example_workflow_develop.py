"""egent 开发工作流示例：主管委派 → 编码 → 验收循环。

运行前请在**当前工作目录**配置 ``.egent/.model.toml``::

    pip install -e .
    python examples/example_workflow_develop.py
"""

from __future__ import annotations

import _common
import conversation_printer
import example_workflow_coding
import example_workflow_review
import egent
import egent.agent


async def begin_develop_workflow(
    description: str,
    *,
    custom_path_permissions: egent.builtin_tools.path_validator.PathPermissions | None = None,
) -> tuple[bool, str]:
    """运行开发工作流：编码与验收循环，直至通过或耗尽重试。

    供程序内调用（如 todo 消化）；注册为 agent 工具请用 ``delegate_develop_workflow``。

    Args:
        description: 开发需求描述。
        custom_path_permissions: 可选的自定义路径权限，透传给 ``coding``；
            为 ``None`` 时使用 ``coding`` 的默认行为。

    Returns:
        (success, summary): success 为 True 表示验收通过。
    """
    ethan = egent.agent.Agent("gpt5-flash")
    ethan.path_permissions = _common.create_egent_path_permissions()
    printer = conversation_printer.ConversationPrinter(ethan)
    ethan.add_message("system", "你是ethan，是这个项目的开发工程师")
    ethan.add_message(
        "system",
        "你收到了新的需求.请做完这个需求并更新单元测试代码.如果任务无法完成,请说明原因并放弃任务.",
    )

    for _ in range(5):
        try:
            finished, _ = await example_workflow_coding.coding(
                ethan, description, custom_path_permissions=custom_path_permissions
            )
        except example_workflow_coding.CodingGaveUp as error:
            return False, f"你的手下放弃了任务。原因是: \n{error.reason}"

        if not finished:
            continue

        passed, accept_message = await example_workflow_review.review(description)
        if passed:
            ethan.add_message(
                "system",
                f"验收通过！请总结本次工作。验收意见:\n{accept_message}",
            )
            await printer.request()
            return True, (
                "工作顺利完成\n\n"
                + ethan.last_message
                + "\n\n---\n验收结果:\n"
                + f"✅ 验收通过\n\n{accept_message}\n\n当前状态:等待提交"
            )

        await ethan.summarize()
        ethan.add_message(
            "system",
            f"验收未通过，请根据验收意见修复:\n\n{accept_message}",
        )

    ethan.add_message("system", "你的工作无法顺利完成。请总结本次工作")
    await printer.request()
    return False, "工作无法顺利完成\n\n" + ethan.last_message


async def delegate_develop_workflow(description: str) -> str:
    """委派开发工作：编码与验收循环，直至通过或耗尽重试。

    @param description 开发需求描述
    """
    _, summary = await begin_develop_workflow(description)
    return summary


async def run_turn(
    agent: egent.agent.Agent,
    printer: conversation_printer.ConversationPrinter,
) -> None:
    """运行一轮交互：收集用户输入并发送请求。"""
    prompt = input(">>> ").strip()
    agent.path_permissions = _common.create_egent_path_permissions()
    if prompt == "/doit":
        agent.add_message(
            "user",
            """
            开始做吧! 你把任务交给你的手下。
            如果这个任务可以拆成独立的多个任务,或者拆成连续的多个步骤,
            那么你就应该拆成多个任务或者多个步骤,依次交给你的手下,每做完一个任务提交一次
            """
        )
        agent.tools = [
            *egent.builtin_tools.git_tools.read_only_tools,
            delegate_develop_workflow,
            egent.builtin_tools.git_tools.git_add,
            egent.builtin_tools.git_tools.git_commit,
        ]
        await printer.request()
        agent.add_message("system", "现在进入询问截断,你暂时不可以委派工作")
    else:
        agent.add_message("user", prompt)
        agent.tools = [
            *egent.builtin_tools.git_tools.read_only_tools,
            egent.builtin_tools.git_tools.git_add,
            egent.builtin_tools.git_tools.git_commit,
            egent.builtin_tools.git_tools.git_push,
        ]
        await printer.request()


async def async_main() -> int:
    """运行交互式聊天，返回进程退出码。"""
    agent = egent.agent.Agent(
        "gpt5",
        skills=(".agents/skills/build-workflow",),
    )
    agent.path_permissions = _common.create_egent_path_permissions()
    agent.add_message(
        "system",
        """你时egent.你是这个agent项目的主管,同时,你就是这个项目驱动的agent.
        和你对接的人是产品经理.你可能需要根据项目的实际情况揣测他背后的真实需求.你需要整理一份大致的计划.计划不要超过10行,每行不要超过160字.
        在产品经理觉得这份计划ok的时候,会给你新的工具,这时候你就可以开始分配任务了
        """,
    )
    printer = conversation_printer.ConversationPrinter(agent)
    while True:
        await run_turn(agent, printer)


if __name__ == "__main__":
    _common.run_cli(async_main)
