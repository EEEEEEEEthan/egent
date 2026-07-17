"""Web 搜索/抓取工具单元测试。"""

# pylint: disable=protected-access,import-error,no-name-in-module,no-member,redefined-outer-name,unused-argument

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import httpx
import pytest

import egent.builtin_tools.web_search_tools as web_search_tools


@pytest.fixture
def mock_ddgs_module():
    """在 sys.modules 中注入 mock duckduckgo_search 模块。"""
    # 若已安装则跳过 mock
    if "duckduckgo_search" in sys.modules:
        yield MagicMock()
        return

    mock_module = types.ModuleType("duckduckgo_search")
    mock_ddgs_cls = MagicMock()
    mock_module.DDGS = mock_ddgs_cls
    sys.modules["duckduckgo_search"] = mock_module
    yield mock_ddgs_cls
    # 清理注入的 mock，避免影响其他测试
    if "duckduckgo_search" in sys.modules:
        del sys.modules["duckduckgo_search"]


def test_web_search_returns_formatted_results(mock_ddgs_module) -> None:
    """web_search 应返回格式化后的搜索结果摘要。"""
    mock_results = [
        {"title": "Python 官网", "href": "https://www.python.org", "body": "Python 是一种编程语言。"},
        {"title": "PEP 8", "href": "https://peps.python.org/pep-0008/", "body": "Python 代码风格指南。"},
    ]

    mock_ddgs_module.return_value.text.return_value = iter(mock_results)

    tool_set = web_search_tools.WebToolSet()
    result = tool_set.web_search("python")

    assert "1. Python 官网" in result
    assert "链接：https://www.python.org" in result
    assert "摘要：Python 是一种编程语言。" in result
    assert "2. PEP 8" in result
    assert "链接：https://peps.python.org/pep-0008/" in result
    assert "摘要：Python 代码风格指南。" in result


def test_web_search_empty_results(mock_ddgs_module) -> None:
    """没有搜索结果时应返回 '(无搜索结果)'。"""
    mock_ddgs_module.return_value.text.return_value = iter([])

    tool_set = web_search_tools.WebToolSet()
    result = tool_set.web_search("nonexistent_xyz")

    assert result == "(无搜索结果)"


def test_web_search_max_results_passed_through(mock_ddgs_module) -> None:
    """max_results 参数应透传给 ddgs.text。"""
    mock_ddgs_module.return_value.text.return_value = iter([])

    tool_set = web_search_tools.WebToolSet()
    tool_set.web_search("test", max_results=5)

    mock_ddgs_module.return_value.text.assert_called_once_with("test", max_results=5)


def test_web_search_handles_exception(mock_ddgs_module) -> None:
    """搜索异常时应返回错误信息而非抛出异常。"""
    mock_ddgs_module.return_value.text.side_effect = RuntimeError("网络错误")

    tool_set = web_search_tools.WebToolSet()
    result = tool_set.web_search("python")

    assert "搜索失败" in result
    assert "网络错误" in result


def test_tools_property_returns_two_tools() -> None:
    """tools 属性应返回包含 web_search 和 web_fetch 的元组。"""
    tool_set = web_search_tools.WebToolSet()
    assert len(tool_set.tools) == 2
    assert tool_set.tools[0] == tool_set.web_search
    assert tool_set.tools[1] == tool_set.web_fetch


def test_web_fetch_returns_plain_text(monkeypatch) -> None:
    """web_fetch 应返回 HTML 剥标签后的纯文本。"""
    html_content = "<html><body><h1>标题</h1><p>正文内容。</p></body></html>"

    def mock_get(url, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.text = html_content
        resp.headers = {"content-type": "text/html"}
        return resp

    monkeypatch.setattr("httpx.get", mock_get)

    tool_set = web_search_tools.WebToolSet()
    result = tool_set.web_fetch("https://example.com")

    assert "标题" in result
    assert "正文内容。" in result
    assert "<html>" not in result


def test_web_fetch_handles_exception(monkeypatch) -> None:
    """web_fetch 异常时应返回错误信息而非抛出异常。"""
    def mock_get(url, **kwargs):
        raise RuntimeError("连接超时")

    monkeypatch.setattr("httpx.get", mock_get)

    tool_set = web_search_tools.WebToolSet()
    result = tool_set.web_fetch("https://example.com")

    assert "抓取失败" in result
    assert "连接超时" in result


def test_web_fetch_empty_content(monkeypatch) -> None:
    """页面内容为空时应返回 '(页面内容为空)'。"""
    def mock_get(url, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.text = ""
        resp.headers = {"content-type": "text/html"}
        return resp

    monkeypatch.setattr("httpx.get", mock_get)

    tool_set = web_search_tools.WebToolSet()
    result = tool_set.web_fetch("https://example.com")

    assert result == "(页面内容为空)"


def test_web_fetch_non_html_content(monkeypatch) -> None:
    """非 HTML 内容（如纯文本）应直接返回。"""
    text_content = "Hello, World!"

    def mock_get(url, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.text = text_content
        resp.headers = {"content-type": "text/plain"}
        return resp

    monkeypatch.setattr("httpx.get", mock_get)

    tool_set = web_search_tools.WebToolSet()
    result = tool_set.web_fetch("https://example.com/file.txt")

    assert result == "Hello, World!"
