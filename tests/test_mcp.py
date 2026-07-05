"""MCP client/manager tests against the in-test echo server (no network)."""
import sys
from pathlib import Path

from clims_core.mcp import StdioMCPClient, MCPManager
from clims_core.tools.base import ToolContext

SERVER = str(Path(__file__).parent / "mcp_echo_server.py")


def test_client_lists_and_calls_tools():
    client = StdioMCPClient(sys.executable, [SERVER], name="echo")
    try:
        client.start()
        tools = client.list_tools()
        names = {t.name for t in tools}
        assert "echo" in names and "add" in names

        text, is_err = client.call_tool("echo", {"text": "hello mcp"})
        assert text == "hello mcp" and not is_err

        text, is_err = client.call_tool("add", {"a": 2, "b": 40})
        assert text == "42" and not is_err
    finally:
        client.close()


def test_manager_wraps_mcp_tools_as_clims_tools():
    mgr = MCPManager()
    try:
        errors = mgr.connect_all({"mcpServers": {
            "echo": {"command": sys.executable, "args": [SERVER]},
        }})
        assert not errors, errors
        tools = mgr.tools()
        names = {t.name for t in tools}
        assert "mcp:echo:echo" in names and "mcp:echo:add" in names

        echo_tool = next(t for t in tools if t.name == "mcp:echo:echo")
        result = echo_tool.run({"text": "via runtime"}, ToolContext())
        assert result.content == "via runtime" and not result.is_error
    finally:
        mgr.close()


def test_unknown_tool_errors_gracefully():
    client = StdioMCPClient(sys.executable, [SERVER], name="echo")
    try:
        client.start()
        try:
            client.call_tool("nope", {})
            assert False, "should have raised"
        except Exception:
            pass
    finally:
        client.close()
