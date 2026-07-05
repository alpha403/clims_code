"""Slash command tests (the side-effecting ones)."""
from pathlib import Path

from clims_cli.repl import _handle_slash
from clims_core.agent.loop import Agent
from clims_core.agent.message import Message
from clims_core.agent.runtime import ToolRuntime
from clims_core.config import Config
from clims_core.permissions.policy import PermissionMode, PermissionPolicy
from clims_core.tools import default_tools, tool_map
from clims_core.tools.base import ToolContext

from tests.fake_provider import FakeProvider


def _agent():
    rt = ToolRuntime(tool_map(default_tools()),
                     PermissionPolicy(mode=PermissionMode.DEFAULT), ToolContext())
    return Agent(provider=FakeProvider([]), model="fake", api_key="k", runtime=rt)


def test_init_creates_clims_md(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _handle_slash("/init", Config(), _agent(), [], {"in": 0, "out": 0})
    assert (tmp_path / "CLIMS.md").exists()
    # second call must not overwrite
    _handle_slash("/init", Config(), _agent(), [], {"in": 0, "out": 0})
    assert "already exists" in capsys.readouterr().out


def test_export_writes_transcript(tmp_path):
    hist = [Message.user("hello"), Message.assistant("hi there")]
    out = tmp_path / "t.md"
    ctrl, _ = _handle_slash(f"/export {out}", Config(), _agent(), hist, {"in": 0, "out": 0})
    assert ctrl == ""
    text = out.read_text(encoding="utf-8")
    assert "hello" in text and "hi there" in text


def test_clear_returns_empty_history():
    ctrl, hist = _handle_slash("/clear", Config(), _agent(), [Message.user("x")],
                               {"in": 0, "out": 0})
    assert ctrl == "" and hist == []


def test_doctor_runs(capsys):
    _handle_slash("/doctor", Config(api_key="set"), _agent(), [], {"in": 0, "out": 0})
    out = capsys.readouterr().out
    assert "clims_code doctor" in out and "providers:" in out


def test_permissions_and_config(capsys):
    _handle_slash("/permissions", Config(), _agent(), [], {"in": 0, "out": 0})
    _handle_slash("/config", Config(api_key="secret"), _agent(), [], {"in": 0, "out": 0})
    out = capsys.readouterr().out
    assert "mode=" in out
    assert "secret" not in out and "***" in out  # key redacted


def test_unknown_command(capsys):
    _handle_slash("/bogus", Config(), _agent(), [], {"in": 0, "out": 0})
    assert "unknown command" in capsys.readouterr().out
