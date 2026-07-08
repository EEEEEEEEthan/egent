"""conversation 单元测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import httpx
from openai import APIStatusError

import egent.conversation
from egent.conversation import _run_with_network_retry


def test_conversation_clone_copies_messages_without_listeners(monkeypatch) -> None:
    """clone 应共享模型配置与技能工具，深拷贝消息，不复制事件监听器。"""
    monkeypatch.setattr(
        "egent.model_settings.ModelSettings.load",
        lambda _profile: SimpleNamespace(
            api_key="test",
            base_url="http://localhost",
            model_name="test-model",
        ),
    )

    leader = egent.conversation.Conversation("test")
    leader.add_message("user", "hello")
    leader.on_event(lambda _event: None)

    reviewer = leader.clone()

    assert reviewer is not leader
    assert reviewer.model == leader.model
    assert reviewer._client is leader._client
    assert reviewer._skill_tools is leader._skill_tools
    assert reviewer.messages == leader.messages
    assert reviewer._messages is not leader._messages
    assert reviewer._event_listeners == []

    leader.add_message("assistant", "world")
    assert leader.messages != reviewer.messages


@pytest.mark.asyncio
async def test_run_with_network_retry_recovers_from_transient_error() -> None:
    """短暂网络异常应自动重试并成功返回。"""
    attempt_count = 0

    async def operation() -> str:
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise httpx.RemoteProtocolError("peer closed")
        return "ok"

    result = await _run_with_network_retry(operation)

    assert result == "ok"
    assert attempt_count == 3


@pytest.mark.asyncio
async def test_run_with_network_retry_reraises_after_exhausted_attempts() -> None:
    """重试耗尽后应原样抛出，不写入对话上下文。"""
    async def operation() -> str:
        raise httpx.RemoteProtocolError("peer closed")

    with pytest.raises(httpx.RemoteProtocolError, match="peer closed"):
        await _run_with_network_retry(operation)


@pytest.mark.asyncio
async def test_run_with_network_retry_does_not_retry_client_errors() -> None:
    """4xx 客户端错误不应重试。"""
    attempt_count = 0

    async def operation() -> str:
        nonlocal attempt_count
        attempt_count += 1
        raise APIStatusError(
            "bad request",
            response=httpx.Response(400, request=httpx.Request("POST", "https://example.com")),
            body=None,
        )

    with pytest.raises(APIStatusError):
        await _run_with_network_retry(operation)

    assert attempt_count == 1
