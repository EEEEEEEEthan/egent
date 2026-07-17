"""Web 搜索/抓取内置工具（使用 duckduckgo-search + httpx，无需 API key）。"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    """用 html.parser 剥标签，积累纯文本。"""

    def __init__(self) -> None:
        """初始化文本提取器。"""
        super().__init__()
        self._text_parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._text_parts.append(data)

    def text(self) -> str:
        """返回累积的纯文本。"""
        return "".join(self._text_parts).strip()


_MAX_FETCH_CHARS = 10000


@dataclass
class WebToolSet:
    """基于 DuckDuckGo 的零配置 Web 搜索 + 页面抓取工具集。"""

    def web_search(self, query: str, max_results: int = 10) -> str:
        """用 DuckDuckGo 搜索，返回格式化摘要。

        @param query 搜索关键词
        @param max_results 返回结果数上限，缺省 10
        """
        # pylint: disable=import-outside-toplevel,import-error
        try:
            from duckduckgo_search import DDGS  # type: ignore[import-untyped]
            results = list(DDGS().text(query, max_results=max_results))
        except ImportError:
            return "搜索失败：需要安装 duckduckgo-search"
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return f"搜索失败：{exc}"

        if not results:
            return "(无搜索结果)"

        lines: list[str] = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', '').strip()}")
            if href := r.get("href", "").strip():
                lines.append(f"   链接：{href}")
            if body := r.get("body", "").strip():
                lines.append(f"   摘要：{body}")
            lines.append("")
        return "\n".join(lines).rstrip("\n")

    def web_fetch(self, url: str) -> str:
        """GET 指定 URL，将 HTML 转为纯文本返回。

        @param url 要抓取的页面地址
        @return 纯文本内容，最长 {_MAX_FETCH_CHARS} 字符
        """
        # pylint: disable=import-outside-toplevel
        try:
            import httpx
            response = httpx.get(url, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "text/" not in content_type and "html" not in content_type:
                text = response.text
            else:
                extractor = _TextExtractor()
                extractor.feed(response.text)
                text = extractor.text()
        except ImportError:
            return "抓取失败：需要安装 httpx"
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return f"抓取失败：{exc}"

        if not text:
            return "(页面内容为空)"

        if len(text) > _MAX_FETCH_CHARS:
            text = text[:_MAX_FETCH_CHARS] + "\n\n…（内容截断）"
        return text

    @property
    def tools(self) -> tuple:
        """全部 Web 工具。"""
        return (self.web_search, self.web_fetch)
