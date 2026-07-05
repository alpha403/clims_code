"""MCP manager — connect configured servers and expose their tools as clims Tools.

An MCPTool adapts one server tool to the clims Tool interface, so MCP tools flow
through the exact same runtime + permission gate as built-ins. Tool names are
namespaced `mcp:<server>:<tool>` to avoid collisions.
"""
from __future__ import annotations

from clims_core.mcp.client import StdioMCPClient, MCPToolSpec
from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult


class MCPTool(Tool):
    # MCP tools can do anything; gate them as NETWORK by default (asked in default mode)
    permission = PermissionClass.NETWORK

    def __init__(self, client: StdioMCPClient, server: str, spec: MCPToolSpec):
        self._client = client
        self._server = server
        self._spec = spec
        self.name = f"mcp:{server}:{spec.name}"
        self.description = spec.description or f"MCP tool {spec.name} from {server}"
        self.input_schema = spec.input_schema or {"type": "object"}
        self._raw_name = spec.name

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        try:
            text, is_error = self._client.call_tool(self._raw_name, input)
        except Exception as e:
            return ToolResult.error(f"{self.name}: {type(e).__name__}: {e}")
        return ToolResult(content=text or "(no content)", is_error=is_error)


class MCPManager:
    """Owns MCP client connections and the tools they expose.

    config shape (see docs/05-MCP.md):
        {"mcpServers": {"name": {"command": "...", "args": [...], "env": {...}}}}
    """
    def __init__(self):
        self.clients: dict[str, StdioMCPClient] = {}
        self._tools: list[MCPTool] = []

    def connect_all(self, config: dict) -> list[str]:
        errors = []
        for name, conf in (config.get("mcpServers") or {}).items():
            try:
                self.connect(name, conf)
            except Exception as e:
                errors.append(f"{name}: {e}")
        return errors

    def connect(self, name: str, conf: dict) -> None:
        if conf.get("url"):
            from clims_core.mcp.http_client import HttpMCPClient
            token = conf.get("token")
            if conf.get("oauth"):
                from clims_core.mcp.oauth import fetch_client_credentials_token
                token = fetch_client_credentials_token(conf["oauth"])
            client = HttpMCPClient(conf["url"], headers=conf.get("headers"),
                                   token=token, name=name)
        elif conf.get("command"):
            client = StdioMCPClient(conf["command"], conf.get("args", []),
                                    conf.get("env"), name=name)
        else:
            raise ValueError("MCP server requires 'command' (stdio) or 'url' (http)")
        client.start()
        self.clients[name] = client
        for spec in client.list_tools():
            self._tools.append(MCPTool(client, name, spec))

    def tools(self) -> list[MCPTool]:
        return list(self._tools)

    def close(self):
        for c in self.clients.values():
            c.close()
        self.clients.clear()
        self._tools.clear()
