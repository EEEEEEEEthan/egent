"""从 Python 函数自动生成 OpenAI 工具 schema。"""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

import pydantic
from openai.lib import pydantic_function_tool
from openai.types.chat.chat_completion_tool_union_param import (
    ChatCompletionToolUnionParam,
)

ToolCallable = Callable[..., Any]
ToolHandler = Callable[[str], str | Awaitable[str]]

_END_CONVERSATION_ATTRIBUTE = "_egent_end_conversation"
_NULL_LITERAL_STRINGS = frozenset({"null", "none", "undefined"})

_PARAM_PATTERN = re.compile(
    r"^\s*@param\s+(\w+)\s*:?\s*(.+)$",
    re.MULTILINE,
)

def end_conversation(function: ToolCallable) -> ToolCallable:
    """标记工具：本轮 tool_calls 全部执行后结束 send()，不再请求模型。"""
    setattr(function, _END_CONVERSATION_ATTRIBUTE, True)
    return function


def function_ends_conversation(function: ToolCallable) -> bool:
    """工具是否带有 end_conversation 标记。"""
    return bool(getattr(function, _END_CONVERSATION_ATTRIBUTE, False))


def sanitize_tool_arguments_json(arguments_json: str) -> str:
    """修正模型常见的 tool arguments JSON 瑕疵（如可选参数写成字符串 \"null\"）。"""
    try:
        parsed_arguments = json.loads(arguments_json)
    except json.JSONDecodeError:
        return arguments_json
    if not isinstance(parsed_arguments, dict):
        return arguments_json
    return json.dumps(_sanitize_json_value(parsed_arguments), ensure_ascii=False)


def tool_from_function(function: ToolCallable) -> ChatCompletionToolUnionParam:
    """把带类型标注与文档注释的函数编成 Chat Completions 工具 schema。"""
    arguments_model = _create_arguments_model(function)
    summary, _ = _parse_docstring(inspect.getdoc(function))
    return pydantic_function_tool(
        arguments_model,
        name=function.__name__,
        description=summary,
    )

def tool_handler_from_function(function: ToolCallable) -> ToolHandler:
    """为函数生成按 JSON 参数调用并返回字符串结果的处理器。"""
    arguments_model = _create_arguments_model(function)

    def handler(arguments_json: str) -> str | Awaitable[str]:
        arguments = arguments_model.model_validate_json(
            sanitize_tool_arguments_json(arguments_json),
        )
        result = function(**arguments.model_dump())
        if inspect.isawaitable(result):
            return _format_awaitable_result(result)
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)

    return handler


def resolve_tools(
    tools: list[ToolCallable],
) -> tuple[
    list[ChatCompletionToolUnionParam],
    dict[str, ToolHandler],
    frozenset[str],
]:
    """把函数列表解析为 API tools、name -> handler 映射与终结聊天工具名集合。

    自动处理重名：首次出现保留原名，后续重名追加 _2、_3 等后缀。
    """
    api_tools: list[ChatCompletionToolUnionParam] = []
    tool_handlers: dict[str, ToolHandler] = {}
    conversation_terminating_tool_names: set[str] = set()
    seen_names: dict[str, int] = {}
    for function in tools:
        api_tool = tool_from_function(function)
        function_name = api_tool["function"]["name"]

        # 检测重名并自动追加后缀
        if function_name in seen_names:
            seen_names[function_name] += 1
            unique_name = f"{function_name}_{seen_names[function_name]}"
        else:
            seen_names[function_name] = 1
            unique_name = function_name

        api_tool["function"]["name"] = unique_name
        api_tools.append(api_tool)
        tool_handlers[unique_name] = tool_handler_from_function(function)
        if function_ends_conversation(function):
            conversation_terminating_tool_names.add(unique_name)
    return api_tools, tool_handlers, frozenset(conversation_terminating_tool_names)


def _create_arguments_model(function: ToolCallable) -> type[pydantic.BaseModel]:
    signature = inspect.signature(function)
    _, parameter_descriptions = _parse_docstring(inspect.getdoc(function))
    field_definitions: dict[str, Any] = {}
    for parameter_name, parameter in signature.parameters.items():
        if parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            raise TypeError(f"工具函数 {function.__name__} 不支持 *args/**kwargs。")

        annotation = (
            str
            if parameter.annotation is inspect.Parameter.empty
            else parameter.annotation
        )
        field_kwargs: dict[str, Any] = {}
        if parameter_name in parameter_descriptions:
            field_kwargs["description"] = parameter_descriptions[parameter_name]
        if parameter.default is not inspect.Parameter.empty:
            field_kwargs["default"] = parameter.default

        if field_kwargs:
            field_definitions[parameter_name] = (
                annotation,
                pydantic.Field(**field_kwargs),
            )
        else:
            field_definitions[parameter_name] = (annotation, ...)

    summary, _ = _parse_docstring(inspect.getdoc(function))
    model = pydantic.create_model(
        f"{function.__name__}Arguments",
        **field_definitions,
    )
    model.__doc__ = summary
    return model


def _parse_docstring(
    docstring: str | None,
) -> tuple[str | None, dict[str, str]]:
    if not docstring:
        return None, {}

    parameter_descriptions = {
        match.group(1): match.group(2).strip()
        for match in _PARAM_PATTERN.finditer(docstring)
    }
    summary_lines = [
        line
        for line in docstring.splitlines()
        if not line.strip().startswith("@param")
    ]
    summary = "\n".join(summary_lines).strip() or None
    return summary, parameter_descriptions

def _sanitize_json_value(value: Any) -> Any:
    if isinstance(value, str) and value.lower() in _NULL_LITERAL_STRINGS:
        return None
    if isinstance(value, dict):
        return {key: _sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_json_value(item) for item in value]
    return value


async def _format_awaitable_result(awaitable: Awaitable[Any]) -> str:
    result = await awaitable
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False)
