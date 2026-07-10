"""将 Agent 流式事件打印到终端。"""

from __future__ import annotations

from types import TracebackType

import egent.agent


class ConversationPrinter:
    """监听 Agent 事件并打印到终端。"""

    def __init__(self, agent: egent.agent.Agent) -> None:
        self._agent = agent
        self._has_text = False
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

    async def request(self) -> None:
        """执行一轮请求并打印流式输出。"""
        await self._agent.request()

    def __handle_event(self, event: egent.agent.AgentEvent) -> None:
        if isinstance(event, egent.agent.TextDelta):
            print(event.text, end="", flush=True)
            self._has_text = True
        elif isinstance(event, egent.agent.ToolCallStarted):
            if self._has_text:
                print(flush=True)
            print(f"[tool_call: {event.name}]", flush=True)
            self._has_text = False
        elif isinstance(event, egent.agent.TurnCompleted):
            print(flush=True)
            self._has_text = False
