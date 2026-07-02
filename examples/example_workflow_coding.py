"""开发编码工作流。

``coding`` 在传入的 ``Conversation`` 上累积上下文，支持多轮修复。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import _common
import egent
import egent.conversation

path_validator = _common.EgentPathValidator()
file_read_tools = egent.builtin_tools.file_system_tools.get_read_tools(path_validator)
file_write_tools = egent.builtin_tools.file_system_tools.get_edit_tools(path_validator)

_TASK_REMINDER = "工作完成后使用 submit_task 工具提交结果，然后回复 `工作结束` 即可"


class CodingGaveUp(Exception):
    """开发者主动放弃任务。"""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


async def coding(
    conversation: egent.conversation.Conversation,
    prompt: str,
    *,
    custom_path_validator: _common.EgentPathValidator | None = None,
) -> tuple[bool, str]:
    """执行一轮开发：按 prompt 实现、提交、跑 pytest。

    会话上下文在多次调用间保持连贯。

    Args:
        conversation: 对话上下文。
        prompt: 开发需求描述。
        custom_path_validator: 可选的自定义路径校验器，用于生成文件写入工具集；
            为 ``None`` 时沿用模块级的 ``file_write_tools``。

    Returns:
        (finished, message): ``finished`` 为 True 表示提交成功且 pytest 通过；
        为 False 表示 pytest 失败，``message`` 为测试输出。

    Raises:
        CodingGaveUp: 开发者放弃任务。
    """
    done = False
    giveup_reason = ""

    def submit_task(success: bool, reason: str) -> str:
        nonlocal done, giveup_reason
        done = success
        giveup_reason = reason
        return "收到"

    write_tools = (
        egent.builtin_tools.file_system_tools.get_edit_tools(custom_path_validator)
        if custom_path_validator is not None
        else file_write_tools
    )

    conversation.add_message("system", f"{prompt}\n\n{_TASK_REMINDER}")
    await _common.request_until_submit_and_print(
        conversation,
        submit_task,
        (
            *file_read_tools,
            *write_tools,
            *egent.builtin_tools.git_tools.read_only_tools,
        ),
    )
    if not done:
        raise CodingGaveUp(giveup_reason)

    pytest_result = subprocess.run(
        [sys.executable, "-m", "pytest"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )
    if pytest_result.returncode == 0:
        conversation.add_message("system", "你的测试通过。")
        return True, "测试通过"

    failure_output = f"{pytest_result.stdout}\n{pytest_result.stderr}".strip()
    conversation.add_message(
        "system",
        f"回归测试失败。请修复:\n\n{failure_output}\n\n请仔细查看需求:\n\n{prompt}",
    )
    return False, failure_output
