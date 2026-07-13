"""agent 单元测试。"""

# pylint: disable=protected-access

from __future__ import annotations

from copy import copy
from types import SimpleNamespace

import pytest
import httpx
import pydantic
from openai import APIStatusError

import egent.agent
import egent.builtin_tools.path_validator
import egent.tool
from egent.agent import _run_with_network_retry


def test_agent_clone_copies_messages_without_listeners(monkeypatch) -> None:
    """clone 应共享模型配置与技能工具，深拷贝消息，不复制事件监听器。"""
    monkeypatch.setattr(
        "egent.model_settings.ModelSettings.load",
        lambda _profile: SimpleNamespace(
            api_key="test",
            base_url="http://localhost",
            model_name="test-model",
        ),
    )

    leader = egent.agent.Agent("test")
    leader.add_message("user", "hello")
    leader.add_listener(lambda _event: None)

    reviewer = copy(leader)

    assert reviewer is not leader
    assert reviewer.model == leader.model
    assert reviewer._Agent__client is leader._Agent__client
    assert reviewer._Agent__builtin_tools is leader._Agent__builtin_tools
    assert reviewer.path_permissions is leader.path_permissions
    assert reviewer.tools == leader.tools
    assert reviewer._Agent__messages == leader._Agent__messages
    assert reviewer._Agent__messages is not leader._Agent__messages
    assert not reviewer._Agent__event_listeners

    leader.add_message("assistant", "world")
    assert leader._Agent__messages != reviewer._Agent__messages


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


def test_agent_includes_builtin_file_tools(monkeypatch) -> None:
    """Agent 应内置文件工具，无需手动加入 tools。"""
    monkeypatch.setattr(
        "egent.model_settings.ModelSettings.load",
        lambda _profile: SimpleNamespace(
            api_key="test",
            base_url="http://localhost",
            model_name="test-model",
        ),
    )

    permissions = egent.builtin_tools.path_validator.PathPermissions(
        discoverable=egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=("*",),
        ),
        readable=egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=("*",),
        ),
        editable=egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=("*",),
        ),
    )
    agent = egent.agent.Agent("test", path_permissions=permissions)

    api_tools, _ = egent.tool.resolve_tools(
        [*egent.builtin_tools.file_system_tools.get_file_tools(agent.path_permissions)],
    )
    tool_names = {tool_schema["function"]["name"] for tool_schema in api_tools}

    assert "read_file" in tool_names
    assert "create_file" in tool_names


@pytest.mark.asyncio
async def test_fetch_chat_completion_falls_back_on_tool_argument_validation_error(
    monkeypatch,
) -> None:
    """流式工具参数解析失败时应回退为非流式请求。"""
    monkeypatch.setattr(
        "egent.model_settings.ModelSettings.load",
        lambda _profile: SimpleNamespace(
            api_key="test",
            base_url="http://localhost",
            model_name="test-model",
        ),
    )

    agent = egent.agent.Agent("test")
    agent.add_message("user", "read foo")

    class BrokenStream:
        """模拟 OpenAI SDK 在 tool arguments 校验阶段抛错。"""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        def __aiter__(self):
            return self

        async def __anext__(self) -> None:
            raise pydantic.ValidationError.from_exception_data(
                "read_fileArguments",
                [
                    pydantic_core_init_error(
                        "limit",
                        "Input should be a valid integer",
                        "int_parsing",
                        "null",
                    ),
                ],
            )

    create_calls: list[dict[str, object]] = []

    async def fake_create(**kwargs: object) -> SimpleNamespace:
        create_calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="fallback text",
                        tool_calls=None,
                    ),
                ),
            ],
        )

    monkeypatch.setattr(
        agent._Agent__client.chat.completions,
        "stream",
        lambda **_kwargs: BrokenStream(),
    )
    monkeypatch.setattr(
        agent._Agent__client.chat.completions,
        "create",
        fake_create,
    )

    text_deltas: list[str] = []
    agent.add_listener(lambda event: text_deltas.append(event.text) if hasattr(event, "text") else None)

    completion = await agent._Agent__fetch_chat_completion([])

    assert len(create_calls) == 1
    assert completion.choices[0].message.content == "fallback text"
    assert text_deltas == ["fallback text"]


def pydantic_core_init_error(
    loc: str,
    message: str,
    error_type: str,
    input_value: object,
) -> dict[str, object]:
    """构造 ValidationError.from_exception_data 所需的 error dict。"""
    return {
        "type": error_type,
        "loc": (loc,),
        "msg": message,
        "input": input_value,
        "url": "https://errors.pydantic.dev/2.13/v/int_parsing",
    }
