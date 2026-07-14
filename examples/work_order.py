"""工单图节点：每个节点绑定一个 Agent，按图结构流转直至叶节点完成。"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import egent.agent

HandoffMessage = str | None
Validator = Callable[[str], str | None]

_COLOR_BLUE = "\033[34m"
_COLOR_RED = "\033[31m"
_COLOR_RESET = "\033[0m"


@dataclass
class WorkOrderNode:
    """工单图中的一个节点，构造时与 Agent、路由与验收逻辑绑定。"""

    name: str
    agent: egent.agent.Agent
    submit_notification: str
    switcher: Callable[[str], tuple[WorkOrderNode | None, HandoffMessage]]
    validator: Validator = field(default=lambda _result: None)

    async def begin(self, prompt: str, history: str = "") -> str:
        """注入本节点提示词并驱动 Agent 运转，直至完成或移交下一节点。"""
        print(f"{_COLOR_BLUE}{self.name} begin{_COLOR_RESET}")
        completion_result: str | None = None
        try:
            await self.agent.await_free()
            await self.agent.summarize()
            if prompt:
                self.agent.add_message("system", prompt)
            while True:
                self.agent.add_message("system", self.submit_notification)
                result = await self.agent.send()
                next_node, handoff_message = self.switcher(result)
                if handoff_message is None:
                    continue
                rejection_reason = self.validator(result)
                if rejection_reason:
                    print(
                        f"{_COLOR_RED}{self.name} auto rejected: {_COLOR_RESET}\n"
                        f"{rejection_reason}"
                    )
                    self.agent.add_message(
                        "user",
                        f"被自动验收打回,原因:\n{rejection_reason}",
                    )
                    continue
                completion_result = result
                extended_history = self.__extend_history(history, handoff_message)
                if next_node is None:
                    return extended_history
                return await next_node.begin("", extended_history)
        finally:
            print(f"{_COLOR_BLUE}{self.name} end{_COLOR_RESET}")
            if completion_result is not None:
                print(completion_result)

    def __extend_history(self, history: str, message: str) -> str:
        segment = f"{self.agent.name}\n{message}"
        if history:
            return f"{history}\n\n{segment}"
        return segment


Switcher = Callable[[str], tuple[WorkOrderNode | None, HandoffMessage]]