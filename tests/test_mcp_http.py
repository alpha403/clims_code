"""HTTP MCP transport test against a mock JSON-RPC-over-HTTP MCP server."""
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from clims_core.mcp import HttpMCPClient, MCPManager
from clims_core.tools.base import ToolContext

TOOLS = [{"name": "ping", "description": "ping", "inputSchema": {"type": "object"}}]


class MockHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        msg = json.loads(self.rfile.read(length) or "{}")
        method, mid = msg.get("method"), msg.get("id")
        if mid is None:  # notification
            self.send_response(202)
            self.end_headers()
            return
        if method == "initialize":
            result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                      "serverInfo": {"name": "mock-http", "version": "1"}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            args = msg.get("params", {}).get("arguments", {})
            result = {"content": [{"type": "text", "text": f"pong:{args.get('x', '')}"}],
                      "isError": False}
        else:
            self._send({"jsonrpc": "2.0", "id": mid,
                        "error": {"code": -32601, "message": "no method"}})
            return
        self._send({"jsonrpc": "2.0", "id": mid, "result": result})

    def _send(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Mcp-Session-Id", "sess-123")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@contextmanager
def mock_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), MockHandler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        srv.shutdown()


def test_http_client_lists_and_calls():
    with mock_server() as url:
        client = HttpMCPClient(url, name="mock").start()
        assert client.session_id == "sess-123"  # captured from response header
        tools = client.list_tools()
        assert [t.name for t in tools] == ["ping"]
        text, is_err = client.call_tool("ping", {"x": "hi"})
        assert text == "pong:hi" and not is_err


def test_manager_connects_http_server():
    with mock_server() as url:
        mgr = MCPManager()
        errors = mgr.connect_all({"mcpServers": {"remote": {"url": url}}})
        assert not errors, errors
        tool = next(t for t in mgr.tools() if t.name == "mcp:remote:ping")
        res = tool.run({"x": "yo"}, ToolContext())
        assert res.content == "pong:yo" and not res.is_error
