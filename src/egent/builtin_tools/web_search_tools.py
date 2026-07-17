"""Web 搜索内置工具（使用 duckduckgo-search，无需 API key）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WebSearchToolSet:
    """基于 DuckDuckGo 的零配置 Web 搜索工具集。"""

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

    @property
    def tools(self) -> tuple:
        """全部 Web 搜索工具。"""
        return (self.web_search,)
