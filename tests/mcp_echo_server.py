"""A minimal in-test MCP server (stdio, newline-delimited JSON-RPC 2.0).

Exposes two tools: `echo` and `add`. Used by test_mcp.py to validate the client
end-to-end without an external dependency.
"""
import json
import sys


TOOLS = [
    {
        "name": "echo",
        "description": "Echo back the provided text.",
        "inputSchema": {"type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"]},
    },
    {
        "name": "add",
        "description": "Add two numbers a and b.",
        "inputSchema": {"type": "object",
                        "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                        "required": ["a", "b"]},
    },
]


def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = msg.get("method")
        mid = msg.get("id")

        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "echo-server", "version": "1.0"},
            }})
        elif method == "notifications/initialized":
            pass  # notification, no response
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
        elif method == "resources/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"resources": [
                {"uri": "mem://note", "name": "note", "mimeType": "text/plain"}]}})
        elif method == "resources/read":
            uri = msg.get("params", {}).get("uri", "")
            send({"jsonrpc": "2.0", "id": mid, "result": {"contents": [
                {"uri": uri, "mimeType": "text/plain", "text": f"content of {uri}"}]}})
        elif method == "prompts/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"prompts": [
                {"name": "greet", "description": "a greeting prompt"}]}})
        elif method == "prompts/get":
            name = msg.get("params", {}).get("name", "")
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "messages": [{"role": "user", "content": {"type": "text",
                                                          "text": f"prompt:{name}"}}]}})
        elif method == "tools/call":
            params = msg.get("params", {})
            name = params.get("name")
            args = params.get("arguments", {})
            if name == "echo":
                text = str(args.get("text", ""))
                send({"jsonrpc": "2.0", "id": mid,
                      "result": {"content": [{"type": "text", "text": text}], "isError": False}})
            elif name == "add":
                total = args.get("a", 0) + args.get("b", 0)
                send({"jsonrpc": "2.0", "id": mid,
                      "result": {"content": [{"type": "text", "text": str(total)}], "isError": False}})
            else:
                send({"jsonrpc": "2.0", "id": mid,
                      "error": {"code": -32601, "message": f"unknown tool {name}"}})
        elif mid is not None:
            send({"jsonrpc": "2.0", "id": mid,
                  "error": {"code": -32601, "message": f"unknown method {method}"}})


if __name__ == "__main__":
    main()
