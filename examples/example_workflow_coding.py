"""开发编码工作流。

``coding`` 在传入的 ``Agent`` 上累积上下文，支持多轮修复。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import _common
import egent
import egent.agent

path_validator = _common.EgentPathValidator()
file_read_tools = egent.builtin_tools.file_system_tools.get_read_tools(path_validator)
file_write_tools = egent.builtin_tools.file_system_tools.get_edit_tools(path_validator)


class CodingGaveUp(Exception):
    """开发者主动放弃任务。"""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


async def coding(
    agent: egent.agent.Agent,
    prompt: str,
    *,
    custom_path_validator: _common.EgentPathValidator | None = None,
) -> tuple[bool, str]:
    """执行一轮开发：按 prompt 实现、提交、跑 pytest。

    会话上下文在多次调用间保持连贯。

    Args:
        agent: 对话上下文。
        prompt: 开发需求描述。
        custom_path_validator: 可选的自定义路径校验器，用于生成文件写入工具集；
            为 ``None`` 时沿用模块级的 ``file_write_tools``。

    Returns:
        (finished, message): ``finished`` 为 True 表示提交成功且 pytest 通过；
        为 False 表示 pytest 失败，``message`` 为测试输出。

    Raises:
        CodingGaveUp: 开发者放弃任务。
    """
    write_tools = (
        egent.builtin_tools.file_system_tools.get_edit_tools(custom_path_validator)
        if custom_path_validator is not None
        else file_write_tools
    )

    agent.add_message("system", prompt)
    agent.tools = [
        *file_read_tools,
        *write_tools,
        *egent.builtin_tools.git_tools.read_only_tools,
    ]
    submitted = await agent.request_submit(
        {"success": (bool, "任务是否完成"), "reason": (str, "放弃任务时说明原因")},
    )
    if not submitted["success"]:
        raise CodingGaveUp(submitted["reason"])

    pytest_result = subprocess.run(
        [sys.executable, "-m", "pytest"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )
    if pytest_result.returncode == 0:
        agent.add_message("system", "你的测试通过。")
        return True, "测试通过"

    failure_output = f"{pytest_result.stdout}\n{pytest_result.stderr}".strip()
    agent.add_message(
        "system",
        f"回归测试失败。请修复:\n\n{failure_output}\n\n请仔细查看需求:\n\n{prompt}",
    )
    return False, failure_output
