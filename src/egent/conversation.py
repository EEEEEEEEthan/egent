"""Chat Completions 多轮对话封装。"""

from __future__ import annotations

import logging
import pathlib
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import pydantic
from openai import AsyncOpenAI, NOT_GIVEN
from openai.lib import pydantic_function_tool
from openai.types.chat import ChatCompletionMessageToolCall
from openai.types.chat.chat_completion_tool_union_param import (
    ChatCompletionToolUnionParam,
)

import egent._line_position
import egent.limits
import egent.model_settings
import egent.builtin_tools.skill_tools
import egent.tool

ChatRole = Literal["system", "user", "assistant", "tool"]
ChatMessage = dict[str, Any]

_EGENT_TEMP_DIR = pathlib.Path.cwd() / ".egent" / ".temp"
_EGENT_LOG_DIR = pathlib.Path.cwd() / ".egent" / ".logs"
_SUBMIT_REMINDER = "工作完成后使用 submit_task 工具提交结果"
_SUMMARIZE_SYSTEM = (
    "请将以下对话历史压缩为简洁摘要，保留关键决策、已完成工作、"
    "当前代码状态与待解决问题。"
)
_SUMMARY_PREFIX = "此前工作摘要:\n"
_SKILL_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_logger = logging.getLogger(__name__)


def build_skills(
    skill_paths: Iterable[str | pathlib.Path],
) -> tuple[dict[str, pathlib.Path], str]:
    """构建技能索引与 system 摘要，单次读取各 SKILL.md。"""
    index: dict[str, pathlib.Path] = {}
    seen_ids: dict[str, int] = {}
    catalog_lines = ["可用技能（使用 learn_skill 查看详情，run_skill_script 运行脚本）:"]
    for raw_path in skill_paths:
        resolved = pathlib.Path(raw_path).resolve()
        skill_dir = resolved.parent if resolved.name == "SKILL.md" and resolved.is_file() else resolved
        skill_md = skill_dir / "SKILL.md"
        frontmatter = _parse_skill_frontmatter(skill_md.read_text(encoding="utf-8")) if skill_md.is_file() else {}
        base_id = frontmatter.get("name", "").strip() or skill_dir.name
        if base_id in seen_ids:
            seen_ids[base_id] += 1
            skill_id = f"{base_id}_{seen_ids[base_id]}"
        else:
            seen_ids[base_id] = 1
            skill_id = base_id
        index[skill_id] = skill_dir
        catalog_lines.append(f"- {skill_id}: {frontmatter.get('description', '').strip()}")
    return index, "\n".join(catalog_lines)


def _parse_skill_frontmatter(content: str) -> dict[str, str]:
    match = _SKILL_FRONTMATTER_PATTERN.match(content)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


_EGENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_PATH = str(_EGENT_LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")
if not any(
    isinstance(handler, logging.FileHandler) and getattr(handler, "baseFilename", None) == _LOG_PATH
    for handler in _logger.handlers
):
    _file_handler = logging.FileHandler(_LOG_PATH, encoding="utf-8")
    _file_handler.setLevel(logging.INFO)
    _file_handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.setLevel(logging.INFO)
    _logger.addHandler(_file_handler)


@dataclass(frozen=True)
class ConversationEvent:
    """Conversation 流式事件基类。"""


@dataclass(frozen=True)
class TextDelta(ConversationEvent):
    """LLM 输出的文本增量。"""

    text: str


@dataclass(frozen=True)
class ToolCallStarted(ConversationEvent):
    """工具调用即将执行。"""

    name: str
    arguments: str


@dataclass(frozen=True)
class ToolCallExecuted(ConversationEvent):
    """工具调用已执行并写回结果。"""

    name: str
    arguments: str
    result: str


@dataclass(frozen=True)
class TurnCompleted(ConversationEvent):
    """单轮对话结束，携带完整回复文本。"""

    text: str



class Conversation:
    """维护 messages 历史并调用 Chat Completions API。"""

    def __init__(
        self,
        settings: str,
        *,
        skills: Iterable[str | pathlib.Path] = (),
    ) -> None:
        """初始化对话会话。

        Args:
            settings: ``.egent/.model.toml`` 中的 profile 名（相对运行目录 ``cwd``）。
            skills: 技能路径列表，每项为技能目录或 ``SKILL.md`` 路径。
        """
        model_settings = egent.model_settings.ModelSettings.load(settings)
        self._client = AsyncOpenAI(
            api_key=model_settings.api_key,
            base_url=model_settings.base_url,
        )
        self.model = model_settings.model_name
        self._messages: list[ChatMessage] = []
        skill_index, skill_catalog = build_skills(skills)
        self.skill_tools = egent.builtin_tools.skill_tools.get_skill_tools(skill_index) if skill_index else []
        if skill_index:
            self.add_message("system", skill_catalog)

    @property
    def messages(self) -> list[ChatMessage]:
        """返回当前聊天记录的副本。"""
        return deepcopy(self._messages)

    @property
    def last_message(self) -> str:
        """返回最后一条消息的 content 文本。"""
        content = self._messages[-1].get("content")
        return content if isinstance(content, str) else ""

    def add_message(self, role: ChatRole, content: str, **extra: Any) -> ChatMessage:
        """追加一条消息，不发起请求。"""
        truncated = _truncate_and_save(content, role)
        message: ChatMessage = {"role": role, "content": truncated, **extra}
        self._messages.append(message)
        extra_text = f" | extra={extra}" if extra else ""
        _logger.info("[%s %s] %s%s", datetime.now().strftime("%H:%M:%S"), role, truncated, extra_text)
        return message

    async def request(
        self,
        *,
        tools: Iterable[egent.tool.ToolCallable] = (),
        resolved_tools: Iterable[tuple[ChatCompletionToolUnionParam, egent.tool.ToolHandler]] = (),
    ) -> AsyncIterator[ConversationEvent]:
        """根据当前历史流式请求助手回复，必要时自动执行工具并续聊。

        Args:
            tools: 普通工具函数列表，自动生成 schema。
            resolved_tools: 已就绪的 (schema, handler) 对，供框架注入
                无法用普通函数表达的工具（如 submit）。
        """
        api_tools, tool_handlers = egent.tool.resolve_tools(list(tools))
        resolved_tools = tuple(resolved_tools)
        api_tools.extend(tool_schema for tool_schema, _ in resolved_tools)
        tool_handlers.update(
            {tool_schema["function"]["name"]: tool_handler for tool_schema, tool_handler in resolved_tools}
        )

        async def run_tool_call(tool_call: ChatCompletionMessageToolCall) -> AsyncIterator[ConversationEvent]:
            function_name = tool_call.function.name
            function_arguments = tool_call.function.arguments
            yield ToolCallStarted(name=function_name, arguments=function_arguments)
            try:
                handler = tool_handlers.get(function_name)
                if handler is None:
                    raise ValueError(f"工具未注册: {function_name}")
                handler_result = handler(function_arguments)
                if isinstance(handler_result, Awaitable):
                    handler_result = await handler_result
            except Exception as exception:  # pylint: disable=broad-exception-caught
                handler_result = str(exception)
            tool_message = self.add_message("tool", handler_result, tool_call_id=tool_call.id)
            yield ToolCallExecuted(
                name=function_name,
                arguments=function_arguments,
                result=tool_message["content"],
            )

        while True:
            async with self._client.chat.completions.stream(
                model=self.model,
                messages=self._messages,
                tools=api_tools if api_tools else NOT_GIVEN,
            ) as stream:
                async for event in stream:
                    if event.type == "content.delta":
                        yield TextDelta(event.delta)
                completion = await stream.get_final_completion()
            message = completion.choices[0].message
            reply_text = message.content or ""
            tool_calls = message.tool_calls or []
            if not tool_calls:
                self.add_message("assistant", reply_text)
                yield TurnCompleted(reply_text)
                return
            self.add_message(
                "assistant",
                reply_text,
                tool_calls=[tool_call.model_dump() for tool_call in tool_calls],
            )
            for tool_call in tool_calls:
                async for tool_event in run_tool_call(tool_call):
                    yield tool_event

    async def request_until_submit(
        self,
        submit_fields: dict[str, tuple[type, str]],
        tools: Iterable[egent.tool.ToolCallable],
        *,
        on_event: Callable[[ConversationEvent], None] | None = None,
    ) -> dict[str, Any]:
        """循环请求直至 ``submit_task`` 工具被调用，返回提交的参数。

        Args:
            submit_fields: submit 参数规格，``字段名 -> (类型, 描述)``。
            tools: 本步可用的工具函数列表。
            on_event: 可选的流式事件回调（如打印到终端）。

        Returns:
            agent 提交的参数，key 与 ``submit_fields`` 一致。
        """
        submit_model = pydantic.create_model(
            "submit_task",
            **{
                field_name: (field_type, pydantic.Field(description=field_description))
                for field_name, (field_type, field_description) in submit_fields.items()
            },
        )
        submit_schema = pydantic_function_tool(
            submit_model,
            name="submit_task",
            description="提交任务结果，结束当前工作循环",
        )
        submitted_arguments: dict[str, Any] | None = None

        def submit_handler(arguments_json: str) -> str:
            nonlocal submitted_arguments
            submitted_arguments = submit_model.model_validate_json(arguments_json).model_dump()
            return "收到"

        tools = tuple(tools)
        self.add_message("system", _SUBMIT_REMINDER)
        while submitted_arguments is None:
            async for event in self.request(
                tools=tools,
                resolved_tools=((submit_schema, submit_handler),),
            ):
                if on_event is not None:
                    on_event(event)
            if submitted_arguments is None:
                self.add_message("system", _SUBMIT_REMINDER)

        return submitted_arguments

    async def summarize(self) -> str:
        """压缩对话历史：保留开头 system 设定，其余合并为一条摘要 system 消息。"""
        system_prefix: list[ChatMessage] = []
        for message in self._messages:
            if message.get("role") != "system":
                break
            system_prefix.append(message)

        rest = self._messages[len(system_prefix):]
        if not rest:
            return ""

        summary_parts: list[str] = []
        for message in rest:
            role = message.get("role", "?")
            content = message.get("content") or ""
            if role == "assistant" and message.get("tool_calls"):
                tool_names = [
                    tool_call["function"]["name"]
                    for tool_call in message["tool_calls"]
                ]
                summary_parts.append(f"[assistant tool_calls: {', '.join(tool_names)}]")
            if content:
                summary_parts.append(f"[{role}]\n{content}")

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _SUMMARIZE_SYSTEM},
                {"role": "user", "content": "\n\n".join(summary_parts)},
            ],
        )
        summary = response.choices[0].message.content or ""
        self._messages = deepcopy(system_prefix)
        self.add_message("system", f"{_SUMMARY_PREFIX}{summary}")
        return summary


def _truncate_and_save(content: str, prefix: str) -> str:
    # 以 TOOL_RESULT_MAX_CHARS 作为截断阈值，超出部分保存到 .egent/.temp/ 临时文件。
    # 原因：工具返回值是一次性的，无其他持久化来源，不保存则 AI 永远无法看到完整内容。
    if len(content) <= egent.limits.TOOL_RESULT_MAX_CHARS:
        return content

    head = content[:egent.limits.TOOL_RESULT_MAX_CHARS]
    tail = content[egent.limits.TOOL_RESULT_MAX_CHARS:]
    _EGENT_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    egent.model_settings.ensure_egent_gitignore()
    file_name = f"{prefix}-{uuid.uuid4().hex}.txt"
    (_EGENT_TEMP_DIR / file_name).write_text(content, encoding="utf-8")
    relative_path = f".egent/.temp/{file_name}"
    file_lines = content.splitlines(keepends=True) or ([content] if content else [])
    next_line, next_column = egent._line_position.position_after_characters(  # pylint: disable=protected-access
        file_lines,
        1,
        1,
        egent.limits.TOOL_RESULT_MAX_CHARS,
    )
    return (
        f"{head}...\n"
        f"(内容太长被截断,剩余{len(tail)}字符,完整内容保存于{relative_path},"
        f"请用 line={next_line} column={next_column} 继续读取)"
    )
