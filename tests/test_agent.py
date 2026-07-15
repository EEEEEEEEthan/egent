"""agent 单元测试。"""

# pylint: disable=protected-access

from __future__ import annotations

import asyncio
from copy import copy
from types import SimpleNamespace

import pytest
import httpx
import pydantic
from openai import APIStatusError

import egent.agent
import egent.builtin_tools.path_validator
import egent.tool


def test_agent_clone_copies_messages_without_listeners(monkeypatch) -> None:
    """clone 应用相同构造参数重建，深拷贝消息，不复制事件监听器。"""
    monkeypatch.setattr(
        "egent.model_settings.ModelSettings.load",
        lambda _profile: SimpleNamespace(
            api_key="test",
            base_url="http://localhost",
            model_name="test-model",
        ),
    )

    leader = egent.agent.Agent(settings="test")
    leader.add_message("user", "hello")
    leader.add_listener(lambda _event: None)

    reviewer = copy(leader)

    assert reviewer is not leader
    assert reviewer.model == leader.model
    assert reviewer._Agent__settings == leader._Agent__settings
    assert reviewer.path_permissions is leader.path_permissions
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

    agent = egent.agent.Agent.__new__(egent.agent.Agent)
    result = await agent._Agent__run_with_network_retry(operation)

    assert result == "ok"
    assert attempt_count == 3


@pytest.mark.asyncio
async def test_run_with_network_retry_reraises_after_exhausted_attempts() -> None:
    """重试耗尽后应原样抛出，不写入对话上下文。"""
    async def operation() -> str:
        raise httpx.RemoteProtocolError("peer closed")

    agent = egent.agent.Agent.__new__(egent.agent.Agent)
    with pytest.raises(httpx.RemoteProtocolError, match="peer closed"):
        await agent._Agent__run_with_network_retry(operation)


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

    agent = egent.agent.Agent.__new__(egent.agent.Agent)
    with pytest.raises(APIStatusError):
        await agent._Agent__run_with_network_retry(operation)

    assert attempt_count == 1


def test_agent_composes_system_prompt_with_skill_catalog(monkeypatch, tmp_path) -> None:
    """构造参数 system_prompt 应与技能目录拼成开头一条 system 消息。"""
    monkeypatch.setattr(
        "egent.model_settings.ModelSettings.load",
        lambda _profile: SimpleNamespace(
            api_key="test",
            base_url="http://localhost",
            model_name="test-model",
        ),
    )
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo\ndescription: 示例技能\n---\n\n# Demo\n",
        encoding="utf-8",
    )

    agent = egent.agent.Agent(
        settings="test",
        system_prompt="你是代码助手。",
        skills=[skill_dir],
    )
    messages = agent._Agent__messages

    assert len(messages) == 1
    assert messages[0]["role"] == "system"
    assert messages[0]["content"].startswith("你是代码助手。\n\n可用技能")
    assert "- demo: 示例技能" in messages[0]["content"]


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

    agent = egent.agent.Agent(settings="test")

    tool_names = {tool_schema["function"]["name"] for tool_schema in agent._Agent__api_tools}

    assert "__read_file__" in tool_names
    assert "__create_file__" in tool_names


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

    agent = egent.agent.Agent(settings="test")
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

    completion = await agent._Agent__fetch_chat_completion()

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


@pytest.mark.asyncio
async def test_send_notifies_when_path_permissions_change(monkeypatch) -> None:
    """path_permissions 变更后，下一轮 completion 前应插入系统通知。"""
    agent = _make_test_agent(monkeypatch)
    agent.path_permissions = egent.builtin_tools.path_validator.PathPermissions(
        discoverable=egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=("/tmp/*",),
        ),
        readable=egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=("/tmp/*",),
        ),
        editable=egent.builtin_tools.path_validator.PathPermissionRule(
            whitelist=(),
            blacklist=("*",),
        ),
    )

    async def fake_fetch_chat_completion() -> SimpleNamespace:
        return _ok_completion()

    monkeypatch.setattr(agent, "_Agent__fetch_chat_completion", fake_fetch_chat_completion)

    await agent.send()

    system_messages = [
        message["content"]
        for message in agent._Agent__messages
        if message["role"] == "system"
    ]
    assert "文件系统权限更新了" in system_messages


@pytest.mark.asyncio
async def test_send_runs_all_tool_calls_before_conversation_terminating_tool(monkeypatch) -> None:
    """终结聊天工具应在本轮全部 tool_calls 执行后再结束 send()。"""
    monkeypatch.setattr(
        "egent.model_settings.ModelSettings.load",
        lambda _profile: SimpleNamespace(
            api_key="test",
            base_url="http://localhost",
            model_name="test-model",
        ),
    )

    execution_order: list[str] = []

    def note_step(step_name: str) -> str:
        """记录执行顺序。

        @param step_name 步骤名
        """
        execution_order.append(step_name)
        return step_name

    @egent.tool.end_conversation
    def finish_task(summary: str) -> str:
        """结束任务。

        @param summary 结果摘要
        """
        execution_order.append(f"finish:{summary}")
        return summary

    agent = egent.agent.Agent(settings="test", tools=[note_step, finish_task])
    fetch_count = 0

    class FakeToolCall:
        def __init__(self, call_id: str, name: str, arguments: str) -> None:
            self.id = call_id
            self.function = SimpleNamespace(name=name, arguments=arguments)

        def model_dump(self) -> dict[str, object]:
            return {
                "id": self.id,
                "function": {
                    "name": self.function.name,
                    "arguments": self.function.arguments,
                },
            }

    async def fake_fetch_chat_completion() -> SimpleNamespace:
        nonlocal fetch_count
        fetch_count += 1
        if fetch_count == 1:
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="",
                            tool_calls=[
                                FakeToolCall("call-1", "note_step", '{"step_name": "first"}'),
                                FakeToolCall("call-2", "finish_task", '{"summary": "done"}'),
                                FakeToolCall("call-3", "note_step", '{"step_name": "last"}'),
                            ],
                        ),
                    ),
                ],
            )
        raise AssertionError("终结聊天工具执行后不应再次请求模型")

    turn_completed_texts: list[str] = []
    agent.add_listener(
        lambda event: turn_completed_texts.append(event.text)
        if isinstance(event, egent.agent.TurnCompleted)
        else None,
    )
    monkeypatch.setattr(agent, "_Agent__fetch_chat_completion", fake_fetch_chat_completion)

    result = await agent.send()

    assert result == "使用了finish_task"
    assert execution_order == ["first", "finish:done", "last"]
    assert fetch_count == 1
    assert turn_completed_texts == ["使用了finish_task"]
    tool_messages = [message for message in agent._Agent__messages if message["role"] == "tool"]
    assert [message["content"] for message in tool_messages] == ["first", "done", "last"]


@pytest.mark.asyncio
async def test_send_blocks_concurrent_send_and_add_message(monkeypatch) -> None:
    """send 进行中时，外部不能重复 send 或 add_message。"""
    monkeypatch.setattr(
        "egent.model_settings.ModelSettings.load",
        lambda _profile: SimpleNamespace(
            api_key="test",
            base_url="http://localhost",
            model_name="test-model",
        ),
    )

    agent = egent.agent.Agent(settings="test")
    send_entered = False

    async def fake_fetch_chat_completion() -> SimpleNamespace:
        nonlocal send_entered
        send_entered = True
        with pytest.raises(RuntimeError, match="不能 add_message"):
            agent.add_message("user", "blocked")
        with pytest.raises(RuntimeError, match="不能重复 send"):
            await agent.send()
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok", tool_calls=[]))],
        )

    monkeypatch.setattr(agent, "_Agent__fetch_chat_completion", fake_fetch_chat_completion)

    assert await agent.send() == "ok"
    assert send_entered
    agent.add_message("user", "after send")


@pytest.mark.asyncio
async def test_send_message_adds_and_sends(monkeypatch) -> None:
    """send_message 追加用户消息并立即 send。"""
    monkeypatch.setattr(
        "egent.model_settings.ModelSettings.load",
        lambda _profile: SimpleNamespace(
            api_key="test",
            base_url="http://localhost",
            model_name="test-model",
        ),
    )

    agent = egent.agent.Agent(settings="test")

    async def fake_fetch_chat_completion() -> SimpleNamespace:
        user_messages = [
            message["content"]
            for message in agent._Agent__messages
            if message["role"] == "user"
        ]
        assert user_messages[-1] == "hello"
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="reply", tool_calls=[]))],
        )

    monkeypatch.setattr(agent, "_Agent__fetch_chat_completion", fake_fetch_chat_completion)

    assert await agent.send_message("user", "hello") == "reply"


def _make_test_agent(monkeypatch) -> egent.agent.Agent:
    monkeypatch.setattr(
        "egent.model_settings.ModelSettings.load",
        lambda _profile: SimpleNamespace(
            api_key="test",
            base_url="http://localhost",
            model_name="test-model",
        ),
    )
    return egent.agent.Agent(settings="test")


def _ok_completion() -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok", tool_calls=[]))],
    )


@pytest.mark.asyncio
async def test_await_free_returns_immediately_when_idle(monkeypatch) -> None:
    """空闲时 await_free 应立即返回且未 busy。"""
    agent = _make_test_agent(monkeypatch)
    await agent.await_free()
    assert not agent.busy


@pytest.mark.asyncio
async def test_await_free_waits_until_send_ends(monkeypatch) -> None:
    """send 进行中时 await_free 应阻塞到结束。"""
    agent = _make_test_agent(monkeypatch)
    release_send = asyncio.Event()

    async def fake_fetch_chat_completion() -> SimpleNamespace:
        await release_send.wait()
        return _ok_completion()

    monkeypatch.setattr(agent, "_Agent__fetch_chat_completion", fake_fetch_chat_completion)

    send_task = asyncio.create_task(agent.send())
    await asyncio.sleep(0)
    assert agent.busy

    wait_task = asyncio.create_task(agent.await_free())
    await asyncio.sleep(0)
    assert not wait_task.done()

    release_send.set()
    await send_task
    await wait_task
    assert not agent.busy
