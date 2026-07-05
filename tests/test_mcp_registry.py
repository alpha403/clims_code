"""MCP server registry: resolve by name, secret routing, add_mcp integration."""
import sys
from pathlib import Path

from clims_core.mcp import registry
from clims_core.agent.runtime import ToolRuntime
from clims_core.permissions.policy import PermissionMode, PermissionPolicy
from clims_core.tools import default_tools, tool_map
from clims_core.tools.base import ToolContext
from clims_core.tools.config_tool import ConfigTool

SERVER = str(Path(__file__).parent / "mcp_echo_server.py")


def test_resolve_token_server_routes_to_env():
    conf = registry.resolve("github", secret="ghp_TOKEN")
    assert conf["command"] == "npx"
    assert "@modelcontextprotocol/server-github" in conf["args"]
    assert conf["env"] == {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_TOKEN"}


def test_resolve_alias_and_secret_as_arg():
    # 'brave' is an alias for brave-search
    assert registry.resolve("brave", secret="K")["env"] == {"BRAVE_API_KEY": "K"}
    # postgres takes the secret (connection string) as an arg, not env
    pg = registry.resolve("postgres", secret="postgres://u:p@h/db")
    assert "postgres://u:p@h/db" in pg["args"] and "env" not in pg


def test_resolve_filesystem_with_extra_arg():
    conf = registry.resolve("filesystem", extra_args=["/data"])
    assert "/data" in conf["args"]


def test_resolve_positional_routed_from_secret():
    # filesystem 'needs' a path; if the value arrives as `secret`, route it to args
    conf = registry.resolve("filesystem", secret="/data")
    assert "/data" in conf["args"] and "env" not in conf


def test_resolve_unknown_is_none():
    assert registry.resolve("totally-made-up") is None
    assert "github" in registry.known_servers()


def test_build_conf_from_name_only(tmp_path):
    cfg = ConfigTool(PermissionPolicy(), tmp_path)
    conf, err = cfg._build_mcp_conf({"name": "slack", "secret": "xoxb-1"})
    assert err is None
    assert conf["env"] == {"SLACK_BOT_TOKEN": "xoxb-1"}


def test_build_conf_unknown_errors(tmp_path):
    cfg = ConfigTool(PermissionPolicy(), tmp_path)
    conf, err = cfg._build_mcp_conf({"name": "nope"})
    assert conf is None and "not a known MCP server" in err


def test_oauth_server_rejected(tmp_path):
    cfg = ConfigTool(PermissionPolicy(), tmp_path)
    _conf, err = cfg._build_mcp_conf({"name": "gdrive", "secret": "x"})
    assert err and "OAuth" in err


def test_add_mcp_by_registry_name_connects(tmp_path, monkeypatch):
    # inject a temp registry entry that points to the local echo server
    monkeypatch.setitem(registry.MCP_SERVERS, "testecho",
                        registry.MCPServerSpec("testecho", command=sys.executable, args=[SERVER]))
    runtime = ToolRuntime(tool_map(default_tools()),
                          PermissionPolicy(mode=PermissionMode.BYPASS), ToolContext(cwd=tmp_path))
    session = {"runtime": runtime, "agent": None}
    cfg = ConfigTool(PermissionPolicy(), tmp_path, session)
    res = cfg.run({"action": "add_mcp", "name": "testecho"}, ToolContext(cwd=tmp_path))
    assert not res.is_error, res.content
    assert "mcp:testecho:add" in runtime.tools
    session.get("mcp_mgr") and session["mcp_mgr"].close()
