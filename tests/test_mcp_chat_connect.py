"""configure add_mcp (live connect from chat) + transcript secret redaction."""
import json
import sys
from pathlib import Path

from clims_core.agent.message import Message
from clims_core.agent.runtime import ToolRuntime
from clims_core.permissions.policy import PermissionMode, PermissionPolicy
from clims_core.redact import redact_secrets
from clims_core.session.store import SQLiteSessionStore
from clims_core.tools import default_tools, tool_map
from clims_core.tools.base import ToolContext
from clims_core.tools.config_tool import ConfigTool

SERVER = str(Path(__file__).parent / "mcp_echo_server.py")


def test_configure_add_mcp_connects_live(tmp_path: Path):
    tools = default_tools()
    runtime = ToolRuntime(tool_map(tools), PermissionPolicy(mode=PermissionMode.BYPASS),
                          ToolContext(cwd=tmp_path))

    class FakeAgent:
        def __init__(self):
            self.tools_schema = []
            self._mcp_mgr = None
    agent = FakeAgent()
    session = {"runtime": runtime, "agent": agent}
    cfg = ConfigTool(PermissionPolicy(), tmp_path, session)

    res = cfg.run({"action": "add_mcp", "name": "echo",
                   "command": sys.executable, "args": [SERVER]}, ToolContext(cwd=tmp_path))
    assert not res.is_error, res.content
    # the MCP tools are now live in the runtime
    assert "mcp:echo:echo" in runtime.tools and "mcp:echo:add" in runtime.tools
    # and advertised to the model
    assert any(s.name == "mcp:echo:add" for s in agent.tools_schema)
    # the new tool actually works
    out = runtime.tools["mcp:echo:add"].run({"a": 2, "b": 5}, ToolContext())
    assert out.content == "7"
    # connection info persisted WITHOUT a command-line secret env
    saved = json.loads((tmp_path / ".clims" / "settings.local.json").read_text())
    assert "echo" in saved["mcpServers"]
    session.get("mcp_mgr") and session["mcp_mgr"].close()


def test_add_mcp_does_not_persist_creds(tmp_path: Path):
    runtime = ToolRuntime(tool_map(default_tools()),
                          PermissionPolicy(mode=PermissionMode.BYPASS), ToolContext(cwd=tmp_path))
    session = {"runtime": runtime, "agent": None}
    cfg = ConfigTool(PermissionPolicy(), tmp_path, session)
    cfg.run({"action": "add_mcp", "name": "echo", "command": sys.executable,
             "args": [SERVER], "env": {"SECRET_TOKEN": "sk-supersecret-123"}},
            ToolContext(cwd=tmp_path))
    saved = (tmp_path / ".clims" / "settings.local.json").read_text()
    assert "sk-supersecret-123" not in saved and "SECRET_TOKEN" not in saved  # creds NOT on disk
    session.get("mcp_mgr") and session["mcp_mgr"].close()


def test_redact_secrets():
    assert "[REDACTED]" in redact_secrets("my key is sk-ant-abc1234567890XYZ here")
    assert "[REDACTED]" in redact_secrets("token=ghp_ABCDEFGHIJ1234567890abcd")
    assert "[REDACTED]" in redact_secrets("API_KEY: sk-1234567890abcdefghij")
    assert redact_secrets("just normal text") == "just normal text"


def test_transcript_redacts_on_persist(tmp_path: Path):
    store = SQLiteSessionStore(str(tmp_path / "s.db"))
    sid = store.create()
    store.set(sid, [Message.user("connect with token ghp_ABCDEFGHIJ1234567890abcd please")])
    raw = (tmp_path / "s.db").read_bytes().decode("utf-8", "replace")
    assert "ghp_ABCDEFGHIJ1234567890abcd" not in raw          # secret not on disk
    assert "[REDACTED]" in store.get(sid)[0].text()
    store.close()
