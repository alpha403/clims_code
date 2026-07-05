"""Batch 3: MCP resources/prompts, OAuth, NotebookEdit, image input, prompt caching."""
import base64
import json
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from clims_core.agent.message import Message, ImageBlock
from clims_core.images import build_image_message
from clims_core.mcp import StdioMCPClient
from clims_core.mcp.oauth import fetch_client_credentials_token
from clims_core.providers.anthropic import AnthropicProvider
from clims_core.tools import NotebookEditTool
from clims_core.tools.base import ToolContext

SERVER = str(Path(__file__).parent / "mcp_echo_server.py")


# ---- MCP resources / prompts ----
def test_mcp_resources_and_prompts():
    client = StdioMCPClient(sys.executable, [SERVER], name="echo")
    try:
        client.start()
        res = client.list_resources()
        assert res and res[0]["uri"] == "mem://note"
        contents = client.read_resource("mem://note")
        assert "content of mem://note" in contents[0]["text"]
        prompts = client.list_prompts()
        assert prompts[0]["name"] == "greet"
        got = client.get_prompt("greet")
        assert "prompt:greet" in json.dumps(got)
    finally:
        client.close()


# ---- MCP OAuth (client-credentials) ----
class _TokenHandler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        self.rfile.read(length)
        body = json.dumps({"access_token": "tok-abc", "token_type": "bearer"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@contextmanager
def _token_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _TokenHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}/token"
    finally:
        srv.shutdown()


def test_oauth_client_credentials():
    with _token_server() as url:
        tok = fetch_client_credentials_token(
            {"token_url": url, "client_id": "id", "client_secret": "secret"})
        assert tok == "tok-abc"


# ---- NotebookEdit ----
def _nb(tmp_path):
    nb = {"cells": [{"cell_type": "code", "source": ["print(1)\n"], "metadata": {},
                     "outputs": [], "execution_count": None}],
          "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
    p = tmp_path / "n.ipynb"
    p.write_text(json.dumps(nb), encoding="utf-8")
    return p


def test_notebook_replace_insert_delete(tmp_path):
    p = _nb(tmp_path)
    ctx = ToolContext(cwd=tmp_path)
    t = NotebookEditTool()
    t.run({"path": "n.ipynb", "cell_number": 0, "new_source": "print(42)", "edit_mode": "replace"}, ctx)
    nb = json.loads(p.read_text(encoding="utf-8"))
    assert "print(42)" in "".join(nb["cells"][0]["source"])
    t.run({"path": "n.ipynb", "cell_number": 0, "new_source": "# title",
           "edit_mode": "insert", "cell_type": "markdown"}, ctx)
    nb = json.loads(p.read_text(encoding="utf-8"))
    assert len(nb["cells"]) == 2 and nb["cells"][0]["cell_type"] == "markdown"
    t.run({"path": "n.ipynb", "cell_number": 0, "cell_number_": 0, "edit_mode": "delete"}, ctx)
    nb = json.loads(p.read_text(encoding="utf-8"))
    assert len(nb["cells"]) == 1


# ---- image input ----
def test_build_image_message(tmp_path):
    img = tmp_path / "pic.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nFAKE")
    m = build_image_message("what is this?", ["pic.png"], cwd=tmp_path)
    assert m.role == "user"
    imgs = [b for b in m.content if isinstance(b, ImageBlock)]
    assert len(imgs) == 1 and imgs[0].media_type == "image/png"
    assert base64.b64decode(imgs[0].data).startswith(b"\x89PNG")


# ---- prompt caching (Anthropic wire) ----
def test_anthropic_prompt_caching_in_system():
    p = AnthropicProvider()
    events = []
    # capture the request body by stubbing _stream
    captured = {}

    def fake_stream(url, api_key, body):
        captured["body"] = body
        from clims_core.providers.base import StreamEvent
        yield StreamEvent.finished("end_turn")

    p._stream = fake_stream
    list(p.chat(model="claude-opus-4-8", messages=[Message.user("hi")],
                system="big system prompt", api_key="k", stream=True))
    sysblock = captured["body"]["system"]
    assert isinstance(sysblock, list)
    assert sysblock[0]["cache_control"]["type"] == "ephemeral"
