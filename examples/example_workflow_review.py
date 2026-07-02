"""开发成果验收工作流。

每次 ``review`` 调用使用独立会话，不保留历史上下文。
"""

from __future__ import annotations

import _common
import egent
import egent.conversation

path_validator = _common.EgentPathValidator()
file_read_tools = egent.builtin_tools.file_system_tools.get_read_tools(path_validator)

_TASK_REMINDER = "工作完成后使用 submit_task 工具提交结果，然后回复 `工作结束` 即可"


async def review(prompt: str) -> tuple[bool, str]:
    """验收开发成果是否满足需求。

    Returns:
        (passed, message): 是否通过验收，及验收意见摘要。
    """
    reviewer = egent.conversation.Conversation("gpt5")
    reviewer.add_message(
        "system",
        "你是这个项目的验收员。你需要验收开发成果是否满足需求。"
        "使用 git_diff 查看代码变更，结合当前项目结构和需求文档进行验收。"
        "\n\n"
        "## 注释审核标准:\n"
        "- 注释中不应硬编码具体数值（如 8000、7200），应引用变量名或常量名\n"
        "- 注释应解释\u201c为什么\u201d这样做，而非重复\u201c做了什么\u201d\n"
        "- 涉及刻意设计决策的代码必须有注释说明意图",
    )
    accepted = False
    accept_summary = ""

    def submit_task(is_accepted: bool, summary: str) -> str:
        nonlocal accepted, accept_summary
        accepted = is_accepted
        accept_summary = summary
        return "收到"

    reviewer.add_message(
        "system",
        f"请验收以下开发成果：\n\n"
        f"## 需求:\n{prompt}\n\n"
        "验收步骤:\n"
        "1. 使用 walk_files 了解项目结构\n"
        "2. 使用 git_diff 确认代码变更范围\n"
        "3. 使用 read_file 仔细检查关键变更文件\n"
        "4. 对照需求逐一核对是否满足\n"
        "5. 使用 submit_task 提交验收结果\n\n"
        f"{_TASK_REMINDER}",
    )
    await _common.request_until_submit_and_print(
        reviewer,
        submit_task,
        (*file_read_tools, *egent.builtin_tools.git_tools.read_only_tools),
    )
    return accepted, accept_summary
