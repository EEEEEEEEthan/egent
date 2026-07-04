"""将 Conversation 流式事件打印到终端。"""

from __future__ import annotations

from collections.abc import Iterable
from types import TracebackType
from typing import Any

import egent.conversation
import egent.tool


class ConversationPrinter:
    """监听 Conversation 事件并打印到终端。"""

    def __init__(self, conversation: egent.conversation.Conversation) -> None:
        self._conversation = conversation
        conversation.on_event(self.__handle_event)

    def close(self) -> None:
        """取消事件监听。"""
        self._conversation.off_event(self.__handle_event)

    def __enter__(self) -> ConversationPrinter:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    async def request(
        self,
        *,
        tools: Iterable[egent.tool.ToolCallable] = (),
        resolved_tools: Iterable[tuple[Any, egent.tool.ToolHandler]] = (),
    ) -> None:
        """执行一轮请求并打印流式输出。"""
        async for _event in self._conversation.request(
            tools=tools,
            resolved_tools=resolved_tools,
        ):
            pass

    def __handle_event(self, event: egent.conversation.ConversationEvent) -> None:
        if isinstance(event, egent.conversation.TextDelta):
            print(event.text, end="", flush=True)
        elif isinstance(event, egent.conversation.ToolCallStarted):
            print(f"\n[tool_call: {event.name}]", flush=True)
        elif isinstance(event, egent.conversation.TurnCompleted):
            print(flush=True)
