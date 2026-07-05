"""HTTP MCP client — JSON-RPC 2.0 over the MCP Streamable HTTP transport.

Complements the stdio client so clims_code can use remote MCP servers. A single
endpoint receives JSON-RPC POSTs and replies with either application/json or an
SSE stream; we handle both. An optional bearer token (e.g. an OAuth access token)
is sent in the Authorization header.
"""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request

from clims_core.mcp.client import MCPError, MCPToolSpec

PROTOCOL_VERSION = "2024-11-05"
_SSL = ssl.create_default_context()


class HttpMCPClient:
    def __init__(self, url: str, headers: dict | None = None,
                 token: str | None = None, name: str = "mcp"):
        self.url = url
        self.extra_headers = dict(headers or {})
        if token:
            self.extra_headers["Authorization"] = f"Bearer {token}"
        self.name = name
        self.session_id: str | None = None
        self._id = 0

    def start(self, timeout: float = 15.0) -> "HttpMCPClient":
        self._request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "clims_code", "version": "0.1.0"},
        }, timeout=timeout)
        self._notify("notifications/initialized", {})
        return self

    # ---- transport ----
    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _headers(self) -> dict:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        h.update(self.extra_headers)
        return h

    def _post(self, payload: dict, timeout: float):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, method="POST")
        for k, v in self._headers().items():
            req.add_header(k, v)
        try:
            resp = urllib.request.urlopen(req, timeout=timeout, context=_SSL)
        except urllib.error.HTTPError as e:
            raise MCPError(f"{self.name}: HTTP {e.code}: "
                           f"{e.read().decode('utf-8', 'replace')[:200]}") from None
        except urllib.error.URLError as e:
            raise MCPError(f"{self.name}: connection error: {e.reason}") from None
        with resp:
            sid = resp.headers.get("Mcp-Session-Id")
            if sid:
                self.session_id = sid
            ctype = resp.headers.get("Content-Type", "")
            body = resp.read().decode("utf-8", "replace")
        return ctype, body

    def _notify(self, method: str, params: dict, timeout: float = 15.0):
        try:
            self._post({"jsonrpc": "2.0", "method": method, "params": params}, timeout)
        except MCPError:
            pass  # notifications are best-effort

    def _request(self, method: str, params: dict, timeout: float = 30.0) -> dict:
        mid = self._next_id()
        ctype, body = self._post(
            {"jsonrpc": "2.0", "id": mid, "method": method, "params": params}, timeout)
        msg = self._extract(ctype, body, mid)
        if "error" in msg:
            err = msg["error"]
            raise MCPError(f"{self.name}: {method} error {err.get('code')}: {err.get('message')}")
        return msg.get("result", {})

    def _extract(self, ctype: str, body: str, mid: int) -> dict:
        if "event-stream" in ctype.lower():
            for line in body.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    try:
                        obj = json.loads(line[len("data:"):].strip())
                    except json.JSONDecodeError:
                        continue
                    if obj.get("id") == mid:
                        return obj
            return {}
        try:
            return json.loads(body) if body else {}
        except json.JSONDecodeError:
            return {}

    # ---- high-level (same surface as StdioMCPClient) ----
    def list_tools(self) -> list[MCPToolSpec]:
        result = self._request("tools/list", {})
        return [
            MCPToolSpec(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema") or t.get("input_schema") or {"type": "object"},
            )
            for t in result.get("tools", [])
        ]

    def list_resources(self) -> list[dict]:
        return self._request("resources/list", {}).get("resources", [])

    def read_resource(self, uri: str) -> list[dict]:
        return self._request("resources/read", {"uri": uri}).get("contents", [])

    def list_prompts(self) -> list[dict]:
        return self._request("prompts/list", {}).get("prompts", [])

    def get_prompt(self, name: str, arguments: dict | None = None) -> dict:
        return self._request("prompts/get", {"name": name, "arguments": arguments or {}})

    def call_tool(self, name: str, arguments: dict, timeout: float = 120.0):
        result = self._request("tools/call", {"name": name, "arguments": arguments},
                               timeout=timeout)
        is_error = bool(result.get("isError", False))
        parts = []
        for block in result.get("content", []) or []:
            parts.append(block.get("text", "") if block.get("type") == "text"
                         else json.dumps(block))
        return ("\n".join(parts), is_error)

    def close(self):
        pass  # stateless HTTP; nothing to tear down
