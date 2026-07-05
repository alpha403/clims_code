"""MCP (Model Context Protocol) client — the capability multiplier.

Lets clims_code connect to any MCP server (stdio today; HTTP/SSE next) and expose
its tools through the same tool runtime the model already uses. This is how the
agent becomes competent at "all digital work" without bespoke tools per app.
"""
from clims_core.mcp.client import StdioMCPClient, MCPError
from clims_core.mcp.http_client import HttpMCPClient
from clims_core.mcp.manager import MCPManager, MCPTool

__all__ = ["StdioMCPClient", "HttpMCPClient", "MCPError", "MCPManager", "MCPTool"]
