"""Chat Completions Agent 封装。"""

from __future__ import annotations

import asyncio
import logging
import pathlib
import re
from src.egent.tool import ToolCallable
import uuid
from collections.abc import Awaitable, Callable, Iterable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import httpx
import pydantic
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, NOT_GIVEN, RateLimitError
from openai.types.chat.chat_completion_tool_union_param import (
    ChatCompletionToolUnionParam,
)

import egent._line_position
import egent.builtin_tools.file_system_tools
import egent.builtin_tools.path_validator
import egent.builtin_tools.skill_tools
import egent.ephemeral_dirs
import egent.limits
import egent.model_settings
import egent.tool

ChatRole = Literal["system", "user", "assistant", "tool"]
ChatMessage = dict[str, Any]

_REQUEST_RETRY_COUNT = 3
_REQUEST_RETRY_DELAY_SECONDS = 2.0
_RETRYABLE_NETWORK_EXCEPTIONS: tuple[type[BaseException], ...] = (
    httpx.HTTPError,
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    APIStatusError,
)
_logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    log_dir = pathlib.Path.cwd() / ".egent" / ".logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = str(log_dir / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")
    if not any(
        isinstance(handler, logging.FileHandler) and getattr(handler, "baseFilename", None) == log_path
        for handler in _logger.handlers
    ):
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        _logger.setLevel(logging.INFO)
        _logger.addHandler(file_handler)
    _logger.propagate = False
    for noisy_logger_name in ("httpx", "httpcore", "openai"):
        logging.getLogger(noisy_logger_name).setLevel(logging.WARNING)
    egent.ephemeral_dirs.prune_oldest_files_in_directory(log_dir)


_configure_logging()


def _sanitize_tool_call_dump(tool_call_dump: dict[str, Any]) -> dict[str, Any]:
    function_payload = tool_call_dump.get("function")
    if not isinstance(function_payload, dict):
        return tool_call_dump
    arguments = function_payload.get("arguments")
    if not isinstance(arguments, str):
        return tool_call_dump
    sanitized_dump = dict(tool_call_dump)
    sanitized_dump["function"] = {
        **function_payload,
        "arguments": egent.tool.sanitize_tool_arguments_json(arguments),
    }
    return sanitized_dump


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
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


async def _run_with_network_retry[_Result](operation: Callable[[], Awaitable[_Result]]) -> _Result:
    """网络异常时静默重试，不写入对话上下文。"""
    last_error: BaseException | None = None
    for attempt_index in range(_REQUEST_RETRY_COUNT):
        try:
            return await operation()
        except _RETRYABLE_NETWORK_EXCEPTIONS as error:
            if isinstance(error, APIStatusError) and error.status_code < 500:
                raise
            last_error = error
            if attempt_index + 1 >= _REQUEST_RETRY_COUNT:
                break
            _logger.warning(
                "网络请求失败，%.0fs 后重试 (%d/%d): %s",
                _REQUEST_RETRY_DELAY_SECONDS,
                attempt_index + 1,
                _REQUEST_RETRY_COUNT,
                error,
            )
            await asyncio.sleep(_REQUEST_RETRY_DELAY_SECONDS)
    assert last_error is not None
    raise last_error


@dataclass(frozen=True)
class AgentEvent:
    """Agent 流式事件基类。"""


@dataclass(frozen=True)
class TextDelta(AgentEvent):
    """LLM 输出的文本增量。"""

    text: str


@dataclass(frozen=True)
class ToolCallStarted(AgentEvent):
    """工具调用即将执行。"""

    name: str
    arguments: str


@dataclass(frozen=True)
class ToolCallExecuted(AgentEvent):
    """工具调用已执行并写回结果。is_exception 为真时 result 为异常内容。"""

    name: str
    arguments: str
    result: str
    is_exception: bool = False


@dataclass(frozen=True)
class TurnCompleted(AgentEvent):
    """单轮对话结束，携带完整回复文本。"""

    text: str



class Agent:  # pylint: disable=too-many-instance-attributes
    """维护 messages 历史并调用 Chat Completions API。"""

    def __init__(
        self,
        settings: str,
        *,
        skills: Iterable[str | pathlib.Path] = (),
        tools: Iterable[egent.tool.ToolCallable] = (),
        path_permissions: egent.builtin_tools.path_validator.PathPermissions | None = None,
    ) -> None:
        """初始化对话会话。

        Args:
            settings: ``.egent/.model.toml`` 中的 profile 名（相对运行目录 ``cwd``）。
            skills: 技能路径列表，每项为技能目录或 ``SKILL.md`` 路径。
            tools: 自定义工具列表，构造后固定不变。
            path_permissions: 文件工具路径权限，构造后固定不变；``None`` 表示不限制。
        """
        model_settings = egent.model_settings.ModelSettings.load(settings)
        self.__client = AsyncOpenAI(
            api_key=model_settings.api_key,
            base_url=model_settings.base_url,
        )
        self.model = model_settings.model_name
        self.tools: tuple[egent.tool.ToolCallable, ...] = tuple[ToolCallable, ...](tools)
        self.path_permissions = path_permissions
        self.__file_tools = egent.builtin_tools.file_system_tools.get_file_tools(path_permissions)
        self.__messages: list[ChatMessage] = []
        self.__event_listeners: list[Callable[[AgentEvent], None]] = []
        skill_index, skill_catalog = build_skills(skills)
        self.__skill_tools = (
            egent.builtin_tools.skill_tools.get_skill_tools(skill_index) if skill_index else []
        )
        if skill_index:
            self.__add_message("system", skill_catalog)

    def __copy__(self) -> Agent:
        cloned = Agent.__new__(Agent)
        state = self.__dict__.copy()
        for key, value in state.items():
            if key.endswith("__messages"):
                state[key] = deepcopy(value)
            elif key.endswith("__event_listeners"):
                state[key] = []
        cloned.__dict__.update(state)
        return cloned

    @property
    def last_message(self) -> str:
        """返回最后一条消息的 content 文本。"""
        content = self.__messages[-1].get("content")
        return content if isinstance(content, str) else ""

    def add_listener(self, listener: Callable[[AgentEvent], None]) -> None:
        """注册流式事件监听器。"""
        self.__event_listeners.append(listener)

    def remove_listener(self, listener: Callable[[AgentEvent], None]) -> None:
        """移除流式事件监听器。"""
        self.__event_listeners.remove(listener)

    def __emit_event(self, event: AgentEvent) -> None:
        for listener in self.__event_listeners:
            listener(event)

    def __add_message(self, role: ChatRole, content: str, **extra: Any) -> ChatMessage:
        """追加消息原文，不截断。供框架写入 agent 回复等。"""
        message: ChatMessage = {"role": role, "content": content, **extra}
        self.__messages.append(message)
        extra_text = f" | extra={extra}" if extra else ""
        _logger.info("[%s %s] %s%s", datetime.now().strftime("%H:%M:%S"), role, content, extra_text)
        return message

    def add_message(self, role: ChatRole, content: str, **extra: Any) -> ChatMessage:
        """追加一条消息，不发起请求。超长内容会截断并落盘。"""
        # 以 TOOL_RESULT_MAX_CHARS 作为截断阈值，超出部分保存到 .egent/.temp/ 临时文件。
        # 原因：工具返回值是一次性的，无其他持久化来源，不保存则 AI 永远无法看到完整内容。
        if len(content) > egent.limits.TOOL_RESULT_MAX_CHARS:
            head = content[:egent.limits.TOOL_RESULT_MAX_CHARS]
            tail = content[egent.limits.TOOL_RESULT_MAX_CHARS:]
            egent_temp_dir = pathlib.Path.cwd() / ".egent" / ".temp"
            egent_temp_dir.mkdir(parents=True, exist_ok=True)
            egent.model_settings.ensure_egent_gitignore()
            file_name = f"{role}-{uuid.uuid4().hex}.txt"
            (egent_temp_dir / file_name).write_text(content, encoding="utf-8")
            egent.ephemeral_dirs.prune_oldest_files_in_directory(egent_temp_dir)
            relative_path = f".egent/.temp/{file_name}"
            file_lines = content.splitlines(keepends=True) or ([content] if content else [])
            next_line, next_column = egent._line_position.position_after_characters(  # pylint: disable=protected-access
                file_lines,
                1,
                1,
                egent.limits.TOOL_RESULT_MAX_CHARS,
            )
            content = (
                f"{head}...\n"
                f"(内容太长被截断,剩余{len(tail)}字符,完整内容保存于{relative_path},"
                f"请用 line={next_line} column={next_column} 继续读取)"
            )
        return self.__add_message(role, content, **extra)

    async def request(self) -> None:
        """根据当前历史请求助手回复，必要时自动执行工具并续聊直至结束。"""
        await self.__request()

    async def __request(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        self,
    ) -> None:
        api_tools, tool_handlers = egent.tool.resolve_tools(
            [*self.__skill_tools, *self.__file_tools, *self.tools],
        )

        while True:
            for attempt_index in range(_REQUEST_RETRY_COUNT):
                try:
                    completion = await self.__fetch_chat_completion(api_tools)
                    break
                except _RETRYABLE_NETWORK_EXCEPTIONS as error:
                    if isinstance(error, APIStatusError) and error.status_code < 500:
                        raise
                    if attempt_index + 1 >= _REQUEST_RETRY_COUNT:
                        raise
                    _logger.warning(
                        "网络请求失败，%.0fs 后重试 (%d/%d): %s",
                        _REQUEST_RETRY_DELAY_SECONDS,
                        attempt_index + 1,
                        _REQUEST_RETRY_COUNT,
                        error,
                    )
                    await asyncio.sleep(_REQUEST_RETRY_DELAY_SECONDS)
            message = completion.choices[0].message
            reply_text = (message.content or "").strip()
            tool_calls = message.tool_calls or []
            if not tool_calls:
                self.__add_message("assistant", reply_text)
                self.__emit_event(TurnCompleted(reply_text))
                return
            self.__add_message(
                "assistant",
                reply_text,
                tool_calls=[
                    _sanitize_tool_call_dump(tool_call.model_dump())
                    for tool_call in tool_calls
                ],
            )
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_arguments = egent.tool.sanitize_tool_arguments_json(
                    tool_call.function.arguments,
                )
                self.__emit_event(ToolCallStarted(name=function_name, arguments=function_arguments))
                is_exception = False
                try:
                    handler = tool_handlers.get(function_name)
                    if handler is None:
                        raise ValueError(f"工具未注册: {function_name}")
                    handler_result = handler(function_arguments)
                    if isinstance(handler_result, Awaitable):
                        handler_result = await handler_result
                except Exception as exception:  # pylint: disable=broad-exception-caught
                    handler_result = str(exception)
                    is_exception = True
                tool_message = self.add_message("tool", handler_result, tool_call_id=tool_call.id)
                self.__emit_event(ToolCallExecuted(
                    name=function_name,
                    arguments=function_arguments,
                    result=tool_message["content"],
                    is_exception=is_exception,
                ))

    async def __fetch_chat_completion(
        self,
        api_tools: list[ChatCompletionToolUnionParam],
    ) -> Any:
        """流式请求 Chat Completion；工具参数解析失败时回退为非流式。"""
        try:
            async with self.__client.chat.completions.stream(
                model=self.model,
                messages=self.__messages,
                tools=api_tools if api_tools else NOT_GIVEN,
            ) as stream:
                async for event in stream:
                    if event.type == "content.delta":
                        self.__emit_event(TextDelta(event.delta))
                return await stream.get_final_completion()
        except pydantic.ValidationError as error:
            _logger.warning("流式工具参数解析失败，回退为非流式请求: %s", error)
            response = await self.__client.chat.completions.create(
                model=self.model,
                messages=self.__messages,
                tools=api_tools if api_tools else NOT_GIVEN,
            )
            reply_text = (response.choices[0].message.content or "").strip()
            if reply_text:
                self.__emit_event(TextDelta(reply_text))
            return response

    async def summarize(self) -> str:
        """压缩对话历史：保留开头 system 设定，其余合并为一条摘要 system 消息。"""
        system_prefix: list[ChatMessage] = []
        for message in self.__messages:
            if message.get("role") != "system":
                break
            system_prefix.append(message)

        rest = self.__messages[len(system_prefix):]
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

        response = await _run_with_network_retry(
            lambda: self.__client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": (
                        "请将以下对话历史压缩为简洁摘要，保留关键决策、已完成工作、"
                        "当前代码状态与待解决问题。"
                    )},
                    {"role": "user", "content": "\n\n".join(summary_parts)},
                ],
            ),
        )
        summary = response.choices[0].message.content or ""
        self.__messages = deepcopy(system_prefix)
        self.__add_message("system", f"此前工作摘要:\n{summary}")
        return summary
