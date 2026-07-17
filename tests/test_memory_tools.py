"""记忆工具单元测试。"""

# pylint: disable=protected-access,import-error,no-name-in-module,no-member

from __future__ import annotations

import re

import pytest

import egent.builtin_tools.memory_tools as memory_tools


def test_memory_read_returns_timestamp_and_content(tmp_path, monkeypatch) -> None:
    """memory_read 应返回时间戳行加剩余内容。"""
    monkeypatch.chdir(tmp_path)
    tool_set = memory_tools.MemoryToolSet("test_agent")
    tool_set.memory_remember("greeting", "你好，世界！\n\n这是第二行。")

    result = tool_set.memory_read("greeting")
    # 格式: YYYY-MM-DD HH:MM:SS\n\n...（第2行开始，含时间戳后的空行）
    assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\n", result), (
        f"期望时间戳前缀，得到: {result!r}"
    )
    rest = result.split("\n", 1)[1] if "\n" in result else ""
    assert rest == "\n你好，世界！\n\n这是第二行。", f"内容不匹配: {rest!r}"


def test_memory_read_raises_on_nonexistent_title() -> None:
    """读取不存在的记忆应抛出 FileNotFoundError。"""
    with pytest.raises(FileNotFoundError, match="记忆不存在：missing"):
        memory_tools.MemoryToolSet("nonexistent_agent").memory_read("missing")
