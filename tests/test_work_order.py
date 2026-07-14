"""work_order 单元测试。"""

from __future__ import annotations

import pytest

import examples.work_order as work_order


class _StubAgent:
    """仅实现 WorkOrderNode 所需接口的测试替身。"""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.messages: list[tuple[str, str]] = []

    def add_message(self, role: str, content: str, **_extra: object) -> dict[str, str]:
        self.messages.append((role, content))
        return {"role": role, "content": content}

    async def send(self) -> str:
        if not self._replies:
            return ""
        return self._replies.pop(0)


@pytest.mark.asyncio
async def test_leaf_node_returns_history_on_valid_submission() -> None:
    """叶节点验收通过后应返回累积历史。"""
    agent = _StubAgent(["完成报告\nDONE"])
    node = work_order.WorkOrderNode(
        agent=agent,  # type: ignore[arg-type]
        sign="review",
        submit_notification="请按格式提交",
        switcher=lambda result: (None, result.removeprefix("完成报告\n") or None),
        validator=lambda result: "太短" if len(result) < 4 else None,
    )

    history = await node.begin("开始审查", "")

    assert history == "review\nDONE"
    assert agent.messages[0] == ("system", "开始审查")
    assert agent.messages[1] == ("system", "请按格式提交")


@pytest.mark.asyncio
async def test_leaf_node_retries_on_validation_failure() -> None:
    """验收失败应打回并继续请求。"""
    agent = _StubAgent(["bad", "完成报告\nOK"])
    reject_count = 0

    def validator(result: str) -> str | None:
        nonlocal reject_count
        if not result.startswith("完成报告"):
            reject_count += 1
            return "格式不对"
        return None

    node = work_order.WorkOrderNode(
        agent=agent,  # type: ignore[arg-type]
        sign="leaf",
        submit_notification="提交",
        switcher=lambda result: (
            None,
            result.removeprefix("完成报告\n")
            if result.startswith("完成报告")
            else result,
        ),
        validator=validator,
    )

    history = await node.begin("", "")

    assert history == "leaf\nOK"
    assert reject_count == 1
    assert any("被自动验收打回" in content for role, content in agent.messages if role == "user")


@pytest.mark.asyncio
async def test_internal_node_hands_off_to_next_node() -> None:
    """中间节点应把累积历史交给下一节点。"""
    leaf_agent = _StubAgent(["完成\nleaf-body"])
    leaf = work_order.WorkOrderNode(
        agent=leaf_agent,  # type: ignore[arg-type]
        sign="leaf",
        submit_notification="leaf-submit",
        switcher=lambda result: (None, result.removeprefix("完成\n") or None),
    )
    root_agent = _StubAgent(["移交\nhandoff-body"])
    root = work_order.WorkOrderNode(
        agent=root_agent,  # type: ignore[arg-type]
        sign="root",
        submit_notification="root-submit",
        switcher=lambda result: (
            (leaf, result.removeprefix("移交\n"))
            if result.startswith("移交\n")
            else (None, None)
        ),
    )

    history = await root.begin("root-prompt", "prior")

    assert history == "prior\n\nroot\nhandoff-body\n\nleaf\nleaf-body"
    assert root_agent.messages[0] == ("system", "root-prompt")
    assert leaf_agent.messages[0] == ("system", "leaf-submit")


@pytest.mark.asyncio
async def test_node_retries_when_switcher_returns_no_message() -> None:
    """未按格式回复时应重复提交轮次。"""
    agent = _StubAgent(["garbage", "完成\nok"])

    def switcher(result: str) -> tuple[work_order.WorkOrderNode | None, str | None]:
        if result.startswith("完成"):
            return None, result.removeprefix("完成\n")
        return None, None

    node = work_order.WorkOrderNode(
        agent=agent,  # type: ignore[arg-type]
        sign="n",
        submit_notification="fmt",
        switcher=switcher,
    )

    await node.begin("", "")

    assert agent._replies == []
    assert sum(1 for _role, _content in agent.messages if _role == "system" and _content == "fmt") == 2
