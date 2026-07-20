"""Chat Completions Agent 封装。"""

# pylint: disable=protected-access

from __future__ import annotations

import asyncio
import logging
import pathlib
from pathlib import Path
import platform
import re
import traceback
import uuid
from collections.abc import Awaitable, Callable, Iterable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import httpx
import pydantic
from openai import (
    NOT_GIVEN,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    LengthFinishReasonError,
    RateLimitError,
)

import egent._line_position
import egent.builtin_tools.env_tools
import egent.builtin_tools.file_system_tools
import egent.builtin_tools.memory_tools
import egent.builtin_tools.path_validator
import egent.builtin_tools.skill_tools
import egent.builtin_tools.web_search_tools
import egent.ephemeral_dirs
import egent._constants
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
_log_path: str = ""  # pylint: disable=invalid-name
_session_guid = uuid.uuid4().hex[:8]  # pylint: disable=invalid-name


def get_log_path() -> str:
    """返回当前日志文件路径。"""
    return _log_path


def get_session_guid() -> str:
    """返回当前会话 GUID。"""
    return _session_guid


def _configure_logging() -> None:
    global _log_path  # pylint: disable=global-statement
    for handler in _logger.handlers:
        if isinstance(handler, logging.FileHandler):
            _log_path = getattr(handler, "baseFilename", _log_path)
            _logger.propagate = False
            for noisy_logger_name in ("httpx", "httpcore", "openai"):
                logging.getLogger(noisy_logger_name).setLevel(logging.WARNING)
            return

    log_dir = egent._constants.EPHEMERAL_ROOT / egent._constants.PROJECT_HASH / _session_guid
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = str((log_dir / "runtime.log").resolve())
    _log_path = log_path
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.setLevel(logging.INFO)
    _logger.addHandler(file_handler)
    _logger.propagate = False
    for noisy_logger_name in ("httpx", "httpcore", "openai"):
        logging.getLogger(noisy_logger_name).setLevel(logging.WARNING)


_configure_logging()
egent.ephemeral_dirs.prune_stale_subdirs(egent._constants.EPHEMERAL_ROOT, max_age_days=10)


@dataclass(frozen=True)
class AgentEvent:
    """Agent 流式事件基类。"""


@dataclass(frozen=True)
class TextDelta(AgentEvent):
    """LLM 输出的文本增量。"""

    text: str


@dataclass(frozen=True)
class ReasoningDelta(AgentEvent):
    """LLM 推理过程的文本增量（reasoning_content）。"""

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



class Agent:  # pylint: disable=too-many-instance-attributes,too-many-arguments
    """维护 messages 历史并调用 Chat Completions API。"""

    def __init__(
        self,
        *,
        settings: str,
        name: str = "",
        system_prompt: str = "",
        skills: Iterable[str | pathlib.Path] = (),
        tools: Iterable[egent.tool.ToolCallable] = (),
        auto_summarize_threshold: int = 100000,
    ) -> None:
        """初始化对话会话。

        Args:
            settings: ``.egent/.model.toml`` 中的 profile 名（相对运行目录 ``cwd``）。
            name: Agent 名称，用于多 Agent 场景标识。
            system_prompt: 系统提示词正文；会与技能目录等拼成一条开头 system 消息。
            skills: 技能路径列表，每项为技能目录或 ``SKILL.md`` 路径。
            tools: 自定义工具列表，构造后固定不变。
            auto_summarize_threshold: tokens 达到此阈值时自动触发摘要压缩。
        """
        self.name = name
        self.auto_summarize_threshold = auto_summarize_threshold
        self.__settings = settings
        self.__system_prompt = system_prompt
        self.__skills = tuple[str | Path, ...](skills)
        self.__tools = tuple[egent.tool.ToolCallable, ...](tools)
        model_settings = egent.model_settings.ModelSettings.load(settings)
        self.__client = AsyncOpenAI(
            api_key=model_settings.api_key,
            base_url=model_settings.base_url,
        )
        self.model = model_settings.model_name
        self.__thinking_mode = model_settings.thinking_mode
        self.__file_system_tool_set = egent.builtin_tools.file_system_tools.FileSystemToolSet()
        self.__path_permissions = egent.builtin_tools.path_validator.PathPermissions(
            readable=egent.builtin_tools.path_validator.PathPermissionRule(
                whitelist=("*", f"{egent._constants.EPHEMERAL_ROOT / egent._constants.PROJECT_HASH / _session_guid}/*"),
            ),
        )
        self.__file_system_tool_set.path_permissions = self.__path_permissions
        self.__memory_tool_set = egent.builtin_tools.memory_tools.MemoryToolSet(self.name)
        self.__web_search_tool_set = egent.builtin_tools.web_search_tools.WebToolSet()
        self.__env_tool_set = egent.builtin_tools.env_tools.EnvToolSet()
        self.__path_permissions_text = self.__path_permissions.format_rules()
        self.__messages: list[ChatMessage] = []
        self.__is_busy = False
        self.__busy_condition = asyncio.Condition()
        self.__event_listeners: list[Callable[[AgentEvent], None]] = []
        self.__tokens: int = 0
        skill_index, skill_catalog = self.__build_skills(skills)
        (
            self.__api_tools,
            self.__tool_handlers,
            self.__conversation_terminating_tool_names,
        ) = egent.tool.resolve_tools(
            [
                *(
                    egent.tool.as_builtin_tool(tool_callable)
                    for tool_callable in (
                        egent.builtin_tools.skill_tools.get_skill_tools(skill_index)
                        if skill_index
                        else []
                    )
                ),
                *(
                    egent.tool.as_builtin_tool(tool_callable)
                    for tool_callable in self.__file_system_tool_set.tools
                ),
                *(
                    egent.tool.as_builtin_tool(tool_callable)
                    for tool_callable in self.__memory_tool_set.tools
                ),
                *(
                    egent.tool.as_builtin_tool(tool_callable)
                    for tool_callable in self.__web_search_tool_set.tools
                ),
                *(
                    egent.tool.as_builtin_tool(tool_callable)
                    for tool_callable in self.__env_tool_set.tools
                ),
                *tools,
            ],
        )
        system_sections = [
            section.strip()
            for section in (system_prompt, skill_catalog if skill_index else "")
            if section.strip()
        ]
        if titles := self.__memory_tool_set.list_titles:
            system_sections.append(f"已有记忆: {', '.join(titles)}")
        if self.__memory_tool_set.tools:
            system_sections.append(
                "你拥有跨会话持久化的记忆系统。每当获得重要信息——如用户偏好、项目约定、关键决策、经验教训等——"
                "你必须主动调用 __bt_memory_remember 写入记忆，而非等用户提醒。每轮对话结束前，回顾本轮内容判断是否需要记录。"
                "查询已有信息时先 __bt_memory_recall 检索，注意记忆可能信息迟滞，需自行判断时效性。"
                "工具: __bt_memory_remember(新建)、__bt_memory_recall(搜索)、__bt_memory_read(阅读完整记忆)、__bt_memory_update(更新)、__bt_memory_forget(删除)。"
            )
        system_sections.append(
            f"操作系统信息: {platform.system()} {platform.release()}"
        )
        system_sections.append(
            "可用 `__bt_get_current_time` 获取当前时间，不要自己猜时间。"
        )
        if system_sections:
            self.__add_message("system", "\n\n".join(system_sections))

    # pylint: disable=protected-access,invalid-name,no-member,attribute-defined-outside-init,unused-private-member
    def __copy__(self) -> Agent:
        cloned = Agent(
            settings=self.__settings,
            name=self.name,
            system_prompt=self.__system_prompt,
            skills=self.__skills,
            tools=self.__tools,
        )
        cloned.__messages = deepcopy(self.__messages)
        cloned.path_permissions = self.path_permissions
        cloned._Agent__path_permissions_text = self._Agent__path_permissions_text
        return cloned

    def add_listener(self, listener: Callable[[AgentEvent], None]) -> None:
        """注册流式事件监听器。"""
        self.__event_listeners.append(listener)

    def remove_listener(self, listener: Callable[[AgentEvent], None]) -> None:
        """移除流式事件监听器。"""
        self.__event_listeners.remove(listener)

    @property
    def path_permissions(self) -> egent.builtin_tools.path_validator.PathPermissions:
        """文件工具路径权限，运行时可修改。"""
        return self.__path_permissions

    @path_permissions.setter
    def path_permissions(
        self,
        value: egent.builtin_tools.path_validator.PathPermissions,
    ) -> None:
        ephemeral_pattern = f"{egent._constants.EPHEMERAL_ROOT / egent._constants.PROJECT_HASH / _session_guid}/*"
        if ephemeral_pattern not in value.readable.whitelist:
            value = egent.builtin_tools.path_validator.PathPermissions(
                discoverable=value.discoverable,
                readable=egent.builtin_tools.path_validator.PathPermissionRule(
                    whitelist=value.readable.whitelist + (ephemeral_pattern,),
                    blacklist=value.readable.blacklist,
                ),
                editable=value.editable,
            )
        self.__path_permissions = value
        self.__file_system_tool_set.path_permissions = value

    @property
    def tokens(self) -> int:
        """当前会话占用的上下文 tokens。"""
        return self.__tokens

    @property
    def busy(self) -> bool:
        """是否正在 send。"""
        return self.__is_busy

    async def await_free(self) -> None:
        """等待 send 结束。

        返回时保证未 busy；若并发等待，先返回的协程可能再次 send，
        其余协程会继续等到下一次空闲。
        """
        async with self.__busy_condition:
            while self.__is_busy:
                await self.__busy_condition.wait()

    def add_message(self, role: ChatRole, content: str, **extra: Any) -> ChatMessage:
        """追加一条消息，不发起请求。超长内容会截断并落盘。"""
        if self.__is_busy:
            raise RuntimeError("Agent 正在 send，不能 add_message")
        return self.__add_message(role, self.__truncate_message_content(role, content), **extra)

    async def send_message(self, role: ChatRole, content: str, reasoning_effort: str | None = None, **extra: Any) -> str:
        """追加一条消息并立即请求助手回复。"""
        self.add_message(role, content, **extra)
        return await self.send(reasoning_effort=reasoning_effort)

    async def send(self, reasoning_effort: str | None = None) -> str:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """根据当前历史请求助手回复，必要时自动执行工具并续聊直至结束。"""
        if self.__is_busy:
            raise RuntimeError("Agent 正在 send，不能重复 send")
        self.__is_busy = True
        try:
            if self.__tokens >= self.auto_summarize_threshold:
                await self.summarize()
            return await self.__send_loop(reasoning_effort=reasoning_effort)
        finally:
            async with self.__busy_condition:
                self.__is_busy = False
                self.__busy_condition.notify_all()

    async def __send_loop(self, reasoning_effort: str | None = None) -> str:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        for _ in range(100):
            self.__sync_path_permissions_notice()
            completion = await self.__run_with_network_retry(lambda: self.__fetch_chat_completion(reasoning_effort))
            if (usage := getattr(completion, 'usage', None)) is not None:
                self.__tokens = usage.total_tokens
            message = completion.choices[0].message
            reply_text = (message.content or "").strip()
            tool_calls = message.tool_calls or []
            if not tool_calls:
                self.__add_message("assistant", reply_text)
                self.__emit_event(TurnCompleted(reply_text))
                return reply_text
            self.__add_message(
                "assistant",
                reply_text,
                tool_calls=[
                    self.__sanitize_tool_call_dump(tool_call.model_dump())
                    for tool_call in tool_calls
                ],
            )
            conversation_terminating_tool_name: str | None = None
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_arguments = egent.tool.sanitize_tool_arguments_json(
                    tool_call.function.arguments,
                )
                self.__emit_event(ToolCallStarted(name=function_name, arguments=function_arguments))
                try:
                    handler = self.__tool_handlers.get(function_name)
                    if handler is None:
                        if function_name.startswith("__bt_"):
                            raise ValueError(
                                f"工具未注册: {function_name}"
                                f"（内置工具须为 __bt_ 前缀格式）",
                            )
                        raise ValueError(f"工具未注册: {function_name}")
                    handler_result = handler(function_arguments)
                    if isinstance(handler_result, Awaitable):
                        handler_result = await handler_result
                except Exception:  # pylint: disable=broad-exception-caught
                    _logger.error("工具调用异常:\n%s", traceback.format_exc().rstrip())
                    handler_result = traceback.format_exc().rstrip("\n")
                    is_exception = True
                else:
                    is_exception = False
                tool_message = self.__add_message(
                    "tool",
                    self.__truncate_message_content("tool", handler_result),
                    tool_call_id=tool_call.id,
                )
                self.__emit_event(ToolCallExecuted(
                    name=function_name,
                    arguments=function_arguments,
                    result=tool_message["content"],
                    is_exception=is_exception,
                ))
                if function_name in self.__conversation_terminating_tool_names:
                    conversation_terminating_tool_name = function_name
            if conversation_terminating_tool_name is not None:
                reply_text = f"使用了{conversation_terminating_tool_name}"
                self.__emit_event(TurnCompleted(reply_text))
                return reply_text
        raise RuntimeError("send_loop 超过 100 轮仍未结束")

    async def summarize(self) -> str:
        """压缩对话历史：保留开头 system 设定，其余合并为一条摘要 system 消息。"""
        system_prefix: list[ChatMessage] = []
        for message in self.__messages:
            if message.get("role") != "system":
                break
            system_prefix.append(message)

        if len(self.__messages) <= len(system_prefix):
            return ""

        summary = ((await self.__client.chat.completions.create(
            model=self.model,
            messages=[
                *deepcopy(system_prefix),
                {"role": "user", "content": "请将以上对话历史压缩为摘要，目标字数约为原文的1/3。保留关键决策、已完成工作、当前代码状态与待解决问题，省略冗余讨论和过程细节。"},
            ],
        )).choices[0].message.content or "").strip()
        self.__messages = deepcopy(system_prefix)
        self.__add_message("system", f"此前工作摘要:\n{summary}")
        print(f"[summarized({self.name})]")
        return summary

    def __sync_path_permissions_notice(self) -> None:
        current_text = self.path_permissions.format_rules()
        if current_text == self.__path_permissions_text:
            return
        self.__path_permissions_text = current_text
        self.__add_message("system", "文件系统权限更新了")

    def __emit_event(self, event: AgentEvent) -> None:
        for listener in self.__event_listeners:
            listener(event)

    def __truncate_message_content(self, role: ChatRole, content: str) -> str:  # pylint: disable=protected-access
        # 以 TOOL_RESULT_MAX_CHARS 作为截断阈值，超出部分保存到 .egent/.temp/ 临时文件。
        # 原因：工具返回值是一次性的，无其他持久化来源，不保存则 AI 永远无法看到完整内容。
        max_chars = egent._constants.TOOL_RESULT_MAX_CHARS
        if len(content) <= max_chars:
            return content
        head = content[:max_chars]
        tail = content[max_chars:]
        egent_temp_dir = egent._constants.EPHEMERAL_ROOT / egent._constants.PROJECT_HASH / _session_guid
        egent_temp_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{role}-{uuid.uuid4().hex}.txt"
        (egent_temp_dir / file_name).write_text(content, encoding="utf-8")
        absolute_path = str((egent_temp_dir / file_name).resolve())
        file_lines = content.splitlines(keepends=True) or ([content] if content else [])
        next_line, next_column = egent._line_position.position_after_characters(
            file_lines,
            1,
            1,
            max_chars,
        )
        return (
            f"{head}...\n"
            f"(内容太长被截断,剩余{len(tail)}字符,完整内容保存于{absolute_path},"
            f"请用 line={next_line} column={next_column} 继续读取)"
        )

    def __add_message(self, role: ChatRole, content: str, **extra: Any) -> ChatMessage:
        """追加消息原文，不截断。供框架写入 agent 回复等。"""
        message: ChatMessage = {"role": role, "content": content, **extra}
        self.__messages.append(message)
        extra_text = f" | extra={extra}" if extra else ""
        _logger.info("[%s %s] %s%s", datetime.now().strftime("%H:%M:%S"), role, content, extra_text)
        return message

    @staticmethod
    def __sanitize_tool_call_dump(tool_call_dump: dict[str, Any]) -> dict[str, Any]:
        function_payload = tool_call_dump.get("function")
        if not isinstance(function_payload, dict):
            return tool_call_dump
        arguments = function_payload.get("arguments")
        if not isinstance(arguments, str):
            return tool_call_dump
        sanitized_dump = dict[str, Any](tool_call_dump)
        sanitized_dump["function"] = {
            **function_payload,
            "arguments": egent.tool.sanitize_tool_arguments_json(arguments),
        }
        return sanitized_dump

    @staticmethod
    def __build_skills(
        skill_paths: Iterable[str | pathlib.Path],
    ) -> tuple[dict[str, pathlib.Path], str]:
        """构建技能索引与 system 摘要，单次读取各 SKILL.md。"""
        index: dict[str, pathlib.Path] = {}
        seen_ids: dict[str, int] = {}
        catalog_lines = ["可用技能（使用 __bt_learn_skill 查看详情，__bt_run_skill_script 运行脚本）:"]
        for raw_path in skill_paths:
            resolved = pathlib.Path(raw_path).resolve()
            skill_dir = resolved.parent if resolved.name == "SKILL.md" and resolved.is_file() else resolved
            skill_md = skill_dir / "SKILL.md"
            frontmatter = Agent.__parse_skill_frontmatter(skill_md.read_text(encoding="utf-8")) if skill_md.is_file() else {}
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

    @staticmethod
    def __parse_skill_frontmatter(content: str) -> dict[str, str]:
        match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return {}
        fields: dict[str, str] = {}
        for line in match.group(1).splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                fields[key.strip()] = value.strip()
        return fields

    @staticmethod
    async def __run_with_network_retry[_Result](operation: Callable[[], Awaitable[_Result]]) -> _Result:
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
                _logger.error(
                    "网络请求失败，%.0fs 后重试 (%d/%d): %s",
                    _REQUEST_RETRY_DELAY_SECONDS,
                    attempt_index + 1,
                    _REQUEST_RETRY_COUNT,
                    error,
                )
                await asyncio.sleep(_REQUEST_RETRY_DELAY_SECONDS)
        assert last_error is not None
        raise last_error

    async def __fetch_chat_completion(self, reasoning_effort: str | None = None) -> Any:
        """流式请求 Chat Completion；工具参数解析失败时回退为非流式。"""
        extra_body = egent.model_settings.build_thinking_extra_body(
            self.__thinking_mode,
            reasoning_effort,
        )
        try:
            async with self.__client.chat.completions.stream(
                model=self.model,
                messages=self.__messages,
                tools=self.__api_tools if self.__api_tools else NOT_GIVEN,
                stream_options={"include_usage": True},
                extra_body=extra_body,
            ) as stream:
                async for event in stream:
                    # 部分网关在 reasoning 阶段会夹带空 content.delta，过滤以免打断思考块。
                    if event.type == "content.delta":
                        if event.delta:
                            self.__emit_event(TextDelta(event.delta))
                    elif event.type == "chunk":
                        for choice in event.chunk.choices:
                            reasoning_text = getattr(choice.delta, "reasoning_content", None)
                            if reasoning_text:
                                self.__emit_event(ReasoningDelta(reasoning_text))
                return await stream.get_final_completion()
        except LengthFinishReasonError as error:
            completion = error.completion
            message = completion.choices[0].message
            if (message.content or "").strip() or message.tool_calls:
                _logger.warning("输出因长度截断，使用部分结果继续")
                return completion
            raise RuntimeError(
                "模型输出达到长度上限且无可用正文/工具调用"
                "（常见原因：思考占满输出额度）。",
            ) from error
        except pydantic.ValidationError as error:
            _logger.error("流式工具参数解析失败，回退为非流式请求: %s", error)
            response = await self.__client.chat.completions.create(
                model=self.model,
                messages=self.__messages,
                tools=self.__api_tools if self.__api_tools else NOT_GIVEN,
                extra_body=extra_body,
            )
            reply_text = (response.choices[0].message.content or "").strip()
            reasoning_text = getattr(response.choices[0].message, "reasoning_content", None)
            if reasoning_text:
                self.__emit_event(ReasoningDelta(reasoning_text))
            if reply_text:
                self.__emit_event(TextDelta(reply_text))
            return response
