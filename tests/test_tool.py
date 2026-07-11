"""tool 模块单元测试。"""

from __future__ import annotations

import json

import pytest

import egent.tool


def add_numbers(left: int, right: int) -> int:
    """两数相加。

    @param left 左操作数
    @param right 右操作数
    """
    return left + right


async def echo_async(message: str) -> str:
    """异步回显。

    @param message 消息内容
    """
    return message


def test_tool_from_function_schema() -> None:
    """tool_from_function 应生成包含参数描述的 schema。"""
    schema = egent.tool.tool_from_function(add_numbers)
    function_schema = schema["function"]

    assert function_schema["name"] == "add_numbers"
    assert function_schema["description"] is not None
    assert "两数相加" in function_schema["description"]
    assert "left" in function_schema["parameters"]["properties"]
    assert "right" in function_schema["parameters"]["properties"]


def test_tool_handler_sync() -> None:
    """同步工具 handler 应返回 JSON 序列化结果。"""
    handler = egent.tool.tool_handler_from_function(add_numbers)
    result = handler('{"left": 1, "right": 2}')

    assert result == json.dumps(3, ensure_ascii=False)


@pytest.mark.asyncio
async def test_tool_handler_async() -> None:
    """异步工具 handler 应返回 await 后的字符串结果。"""
    handler = egent.tool.tool_handler_from_function(echo_async)
    result = handler('{"message": "hello"}')

    assert await result == "hello"


def test_resolve_tools() -> None:
    """resolve_tools 应同时生成 API tools 与 name 到 handler 的映射。"""
    api_tools, handlers = egent.tool.resolve_tools([add_numbers, echo_async])

    assert len(api_tools) == 2
    assert handlers["add_numbers"]('{"left": 3, "right": 4}') == "7"
    assert "echo_async" in handlers


def broken_tool(message: str) -> str:
    """会抛出异常的工具。

    @param message 消息内容
    """
    raise RuntimeError(message)


async def broken_async_tool(message: str) -> str:
    """会抛出异常的异步工具。

    @param message 消息内容
    """
    raise RuntimeError(message)


def test_tool_handler_raises_exception_on_error() -> None:
    """同步工具 handler 遇到未预期异常时应直接向上抛出。"""
    handler = egent.tool.tool_handler_from_function(broken_tool)

    with pytest.raises(RuntimeError, match="boom"):
        handler('{"message": "boom"}')


def test_tool_handler_raises_on_invalid_arguments() -> None:
    """参数校验失败时应直接向上抛出异常。"""
    handler = egent.tool.tool_handler_from_function(add_numbers)

    with pytest.raises(Exception):
        handler('{"left": "not-a-number", "right": 1}')


@pytest.mark.asyncio
async def test_tool_handler_async_raises_exception_on_error() -> None:
    """异步工具 handler 遇到未预期异常时应直接向上抛出。"""
    handler = egent.tool.tool_handler_from_function(broken_async_tool)
    result = handler('{"message": "boom"}')

    with pytest.raises(RuntimeError, match="boom"):
        await result


def test_resolve_tools_deduplicate_names() -> None:
    """resolve_tools 应对重名函数自动追加后缀 _2、_3。"""
    def greet(name: str) -> str:
        """问候。

        @param name 名字
        """
        return f"Hello, {name}!"

    # 两个函数同名（用同一个函数模拟重名场景）
    api_tools, handlers = egent.tool.resolve_tools([greet, greet])

    assert len(api_tools) == 2
    assert api_tools[0]["function"]["name"] == "greet"
    assert api_tools[1]["function"]["name"] == "greet_2"

    assert "greet" in handlers
    assert "greet_2" in handlers
    assert "greet_3" not in handlers

    # 验证 handler 正常工作
    assert handlers["greet"]('{"name": "Alice"}') == "Hello, Alice!"
    assert handlers["greet_2"]('{"name": "Bob"}') == "Hello, Bob!"


def test_resolve_tools_multiple_duplicates() -> None:
    """resolve_tools 应对多个重名依次追加 _2、_3、_4。"""
    def calc(x: int) -> int:
        """计算。

        @param x 数值
        """
        return x * 2

    api_tools, handlers = egent.tool.resolve_tools([calc, calc, calc, calc])

    assert len(api_tools) == 4
    assert api_tools[0]["function"]["name"] == "calc"
    assert api_tools[1]["function"]["name"] == "calc_2"
    assert api_tools[2]["function"]["name"] == "calc_3"
    assert api_tools[3]["function"]["name"] == "calc_4"

    assert set(handlers.keys()) == {"calc", "calc_2", "calc_3", "calc_4"}


def test_varargs_not_supported() -> None:
    """带 *args 的工具函数应被拒绝。"""
    def bad_tool(*_arguments: str) -> str:
        return ""

    with pytest.raises(TypeError, match="不支持"):
        egent.tool.tool_from_function(bad_tool)


def test_sanitize_tool_arguments_json_fixes_string_null() -> None:
    """sanitize 应把字符串 null 转为 JSON null。"""
    sanitized = egent.tool.sanitize_tool_arguments_json(
        '{"path": "foo.txt", "limit": "null"}',
    )

    assert json.loads(sanitized) == {"path": "foo.txt", "limit": None}


def test_tool_handler_accepts_string_null_optional_argument() -> None:
    """handler 应容错模型把可选整数写成字符串 null。"""
    def read_file(path: str, limit: int | None = None) -> str:
        """读取文件。

        @param path 文件路径
        @param limit 行数上限
        """
        return f"{path}:{limit}"

    handler = egent.tool.tool_handler_from_function(read_file)
    result = handler('{"path": "foo.txt", "limit": "null"}')

    assert result == "foo.txt:None"
