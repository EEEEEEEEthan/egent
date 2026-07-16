"""记忆工具单元测试。"""

# pylint: disable=protected-access,import-error,no-name-in-module,no-member

from __future__ import annotations

import pytest

import egent.builtin_tools.memory_tools as memory_tools


def test_memory_read_returns_full_content(tmp_path, monkeypatch) -> None:
    """memory_read 应返回 .md 文件的完整内容。"""
    monkeypatch.chdir(tmp_path)
    tool_set = memory_tools.MemoryToolSet("test_agent")
    tool_set.memory_remember("greeting", "你好，世界！\n\n这是第二行。")

    assert tool_set.memory_read("greeting") == "你好，世界！\n\n这是第二行。"


def test_memory_read_raises_on_nonexistent_title() -> None:
    """读取不存在的记忆应抛出 FileNotFoundError。"""
    with pytest.raises(FileNotFoundError, match="记忆不存在：missing"):
        memory_tools.MemoryToolSet("nonexistent_agent").memory_read("missing")
