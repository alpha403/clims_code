"""web_search tool — search the web for current information.

Default backend is DuckDuckGo's HTML endpoint (no API key required). The HTML
parser is separated from the network call so it can be unit-tested deterministically.
A future BYO search API (Brave/Serper/Tavily) can slot in behind the same tool.
"""
from __future__ import annotations

import html as _html
import re
import urllib.parse

from clims_core.http import post_form, HTTPError
from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult

_LINK_RE = re.compile(r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL)
_SNIPPET_RE = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return _html.unescape(_TAG_RE.sub("", text)).strip()


def _decode_href(href: str) -> str:
    # DuckDuckGo wraps targets as //duckduckgo.com/l/?uddg=<encoded>&...
    m = re.search(r"uddg=([^&]+)", href)
    if m:
        return urllib.parse.unquote(m.group(1))
    if href.startswith("//"):
        return "https:" + href
    return href


def parse_ddg_html(html_text: str, max_results: int = 8) -> list[dict]:
    titles = _LINK_RE.findall(html_text)
    snippets = _SNIPPET_RE.findall(html_text)
    results = []
    for i, (href, title) in enumerate(titles[:max_results]):
        snippet = _clean(snippets[i]) if i < len(snippets) else ""
        results.append({
            "title": _clean(title),
            "url": _decode_href(href),
            "snippet": snippet,
        })
    return results


def search_web(query: str, max_results: int = 8) -> list[dict]:
    """Structured search: returns [{title,url,snippet}]. Used by the research harness."""
    _ctype, body = post_form("https://html.duckduckgo.com/html/", {"q": query}, timeout=30)
    return parse_ddg_html(body, max_results)


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Search the web and return a list of result titles, URLs, and snippets. "
        "Use for current events, facts, docs, or to find pages to read with web_fetch."
    )
    permission = PermissionClass.NETWORK
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "description": "default 8"},
        },
        "required": ["query"],
    }

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        query = input.get("query")
        if not query:
            return ToolResult.error("web_search: 'query' is required")
        max_results = int(input.get("max_results", 8))
        # DuckDuckGo's HTML endpoint requires a form POST (GET returns no results).
        try:
            _ctype, body = post_form("https://html.duckduckgo.com/html/",
                                     {"q": query}, timeout=30)
        except HTTPError as e:
            return ToolResult.error(f"web_search: HTTP {e.status}: {e.body[:200]}")
        except Exception as e:
            return ToolResult.error(f"web_search: {type(e).__name__}: {e}")

        results = parse_ddg_html(body, max_results)
        if not results:
            return ToolResult.ok("(no results)")
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}")
        return ToolResult.ok("\n".join(lines))
