"""egent 聊天 CLI 示例。

运行前请在**当前工作目录**配置 ``.egent/.model.toml``::

    python examples/example_agent.py
"""

from __future__ import annotations

import asyncio
import re
import traceback
from pathlib import Path

import _bootstrap  # noqa: F401  # pylint: disable=unused-import  # 必须在 import egent 之前
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings

import conversation_printer
import shell_tools
import workflow
import egent.agent
import egent.builtin_tools.path_validator
import egent.builtin_tools.test_tools
from examples import hot_reload


async def run() -> int:
    """运行交互式聊天，返回进程退出码。"""
    try:
        while True:
            await chat()
    except (EOFError, KeyboardInterrupt):
        print()
        return 0

async def chat():
    """运行交互式聊天，返回进程退出码。"""

    async def assign(title: str, description: str) -> str:
        """开发 - 启动开发工作流。上下文会保持
        @param title: 工作流标题,几个单词即可
        @param description: 需求文本.请描述需求背景和精准的需求内容.由于上下文会保持,第二次assign开始可以直接描述修订方案,而不必重复背景.
        """
        nonlocal leader

        def discard_unstaged_changes() -> str:
            _, restore_output = shell_tools.run_command("git", "restore", ".")
            _, clean_output = shell_tools.run_command("git", "clean", "-fd")
            return "\n".join(part for part in (restore_output, clean_output) if part)

        shell_tools.run_command("git", "add", "-A")
        try:
            success, report = await wf.assign(description, title)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            report = (
                f"开发工作流异常：{type(exc).__name__}: {exc}\n\n"
                f"{traceback.format_exc()}"
            )
            print(f"\033[31m{report}\033[0m")
            git_output = discard_unstaged_changes()
            if git_output:
                report += f"\n\n{git_output}"
            return report
        report = f"{report}\n\n开发日志见 {wf.log_path}"
        if not success:
            git_output = discard_unstaged_changes()
            if git_output:
                report += f"\n\n{git_output}"
            report += "\n\n请考虑调整需求描述重新委派开发工作或者与用户重新讨论需求."
        return report

    def git_commit(commit_message: str) -> str:
        """提交变更。
        @param commit_message: 提交信息
        """
        version = None
        path = Path("pyproject.toml")
        text = path.read_text(encoding="utf-8")
        match = re.search(r'^version = "(\d+)\.(\d+)\.(\d+)"', text, re.MULTILINE)
        if match:
            version = f"{match.group(1)}.{match.group(2)}.{int(match.group(3)) + 1}"
            path.write_text(text[:match.start()] + f'version = "{version}"' + text[match.end():], encoding="utf-8")
        returncode, _ = shell_tools.run_command("git", "add", "-A")
        if returncode != 0:
            return "git add 失败"
        returncode, commit_output = shell_tools.run_command("git", "commit", "-m", commit_message)
        if returncode != 0:
            return f"git 提交失败：\n{commit_output or ''}"
        if version:
            return f"已提交 v{version}"
        return commit_output or "git 提交成功"
    leader = egent.agent.Agent(
        name="ethan",
        settings="leader",
        system_prompt=(
            "你是ethan，你是这个项目的主程\n"
            "用户是资深程序员，也是制作人，沟通时不需要解释太多\n"
            "如果他让你修改项目,你需要提出方案.你提出方案之后需要和他核对,在他明确表达可以开始执行了你才可以开始执行\n"
            "你给出的方案应该措辞精炼,不要说废话.以最简洁的方式给出方案.\n"
            f"执行修改请使用{assign.__name__},而不要亲自执行.为了防止你事必躬亲,我拿掉了你的编辑权限(哈哈)\n"
        ),
        tools=(assign, egent.builtin_tools.test_tools.run_regression_test, git_commit),
    )
    wf = workflow.Workflow(leader)
    leader.path_permissions = egent.builtin_tools.path_validator.PathPermissions(
        discoverable=workflow.DISCOVERABLE_RULE,
        readable=workflow.READABLE_RULE,
        editable=workflow.NO_EDITABLE_RULE,
    )
    leader.add_message("system", f"日志文件路径: {egent.agent.get_log_path()}")
    conversation_printer.ConversationPrinter(leader)
    bindings = KeyBindings()

    @bindings.add("c-enter")
    def _(event):
        event.current_buffer.validate_and_handle()

    session = PromptSession(
        ">>> ",
        key_bindings=bindings,
        history=FileHistory(".example_agent_history"),
        multiline=True,
    )
    while True:
        user_input = session.prompt().strip()
        if not user_input:
            continue
        if user_input == "/clear":
            break
        leader.add_message("user", user_input)
        await leader.send(reasoning_effort="high")
        pct = leader.tokens / leader.auto_summarize_threshold * 100
        print(f"[tokens({leader.name}): {leader.tokens/1000:.1f}k, {pct:.0f}%]")
        hot_reload(leader)

if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
