"""web_fetch tool — fetch a URL and return readable text.

Strips HTML to text with a stdlib parser (no bs4). NETWORK permission class.
"""
from __future__ import annotations

from html.parser import HTMLParser

from clims_core.http import get_text, HTTPError
from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult

MAX_CHARS = 20000


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks: list[str] = []
        self._skip = 0  # depth inside script/style

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip:
            return
        text = data.strip()
        if text:
            self._chunks.append(text)

    def text(self) -> str:
        return "\n".join(self._chunks)


def fetch_url_text(url: str, max_chars: int = MAX_CHARS) -> str:
    """Fetch a URL and return readable text (HTML stripped). Used by the research harness."""
    try:
        ctype, body = get_text(url)
    except Exception:
        return ""
    if "html" in ctype.lower():
        parser = _TextExtractor()
        try:
            parser.feed(body)
            body = parser.text()
        except Exception:
            pass
    return body[:max_chars]


class WebFetchTool(Tool):
    name = "web_fetch"
    description = (
        "Fetch a URL over HTTP(S) and return its readable text content "
        "(HTML is stripped to text). Use for reading docs, pages, and APIs."
    )
    permission = PermissionClass.NETWORK
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "http(s) URL to fetch."},
        },
        "required": ["url"],
    }

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        url = input.get("url")
        if not url:
            return ToolResult.error("web_fetch: 'url' is required")
        if not url.startswith(("http://", "https://")):
            return ToolResult.error("web_fetch: url must start with http:// or https://")
        try:
            ctype, body = get_text(url)
        except HTTPError as e:
            return ToolResult.error(f"web_fetch: HTTP {e.status} for {url}: {e.body[:200]}")
        except Exception as e:
            return ToolResult.error(f"web_fetch: {type(e).__name__}: {e}")

        if "html" in ctype.lower():
            parser = _TextExtractor()
            try:
                parser.feed(body)
                body = parser.text()
            except Exception:
                pass  # fall back to raw body
        if len(body) > MAX_CHARS:
            body = body[:MAX_CHARS] + f"\n…[truncated, {len(body) - MAX_CHARS} more chars]"
        return ToolResult.ok(body or "(empty response)")
