"""将 Agent 流式事件打印到终端。"""

from __future__ import annotations

import _bootstrap  # noqa: F401

from types import TracebackType

import egent.agent


class ConversationPrinter:
    """监听 Agent 事件并打印到终端。"""

    def __init__(self, agent: egent.agent.Agent, indent_level: int = 0) -> None:
        self._agent = agent
        self._indent_prefix = "  " * indent_level
        self._has_text = False
        self._at_line_start = True
        agent.add_listener(self.__handle_event)

    def close(self) -> None:
        """取消事件监听。"""
        self._agent.remove_listener(self.__handle_event)

    def __enter__(self) -> ConversationPrinter:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    async def send(self) -> None:
        """执行一轮请求并打印流式输出。"""
        await self._agent.send()

    def __print(self, text: str, *, end: str = "\n") -> None:
        payload = f"{text}{end}"
        if not self._indent_prefix:
            print(payload, end="", flush=True)
            return
        for character in payload:
            if character == "\n":
                print("\n", end="", flush=True)
                self._at_line_start = True
                continue
            if self._at_line_start:
                print(self._indent_prefix, end="", flush=True)
                self._at_line_start = False
            print(character, end="", flush=True)

    def __handle_event(self, event: egent.agent.AgentEvent) -> None:
        if isinstance(event, egent.agent.TextDelta):
            self.__print(event.text, end="")
            self._has_text = True
        elif isinstance(event, egent.agent.ToolCallStarted):
            if self._has_text:
                self.__print("", end="\n")
            self.__print(f"[tool_call: {event.name}]")
            self._has_text = False
        elif isinstance(event, egent.agent.TurnCompleted):
            self.__print("", end="\n")
            self._has_text = False
