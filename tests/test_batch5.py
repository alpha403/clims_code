"""Batch 5: telemetry, updater, keybindings, diagnostics, notify, input queue, vim."""
import json
from pathlib import Path

from clims_cli.input_queue import MessageQueue
from clims_cli.notify import notify
from clims_cli.prompt import Input, prompt_toolkit_available
from clims_core.diagnostics import load_diagnostics, format_diagnostics
from clims_core.keybindings import load_keybindings, DEFAULTS
from clims_core.telemetry import Telemetry
from clims_core.updater import current_version, update_command, update


def test_telemetry_opt_in(tmp_path: Path):
    log = tmp_path / "t.log"
    off = Telemetry(enabled=False, path=log)
    off.event("turn", model="x")
    assert not log.exists()  # disabled writes nothing
    on = Telemetry(enabled=True, path=log, clock=lambda: 1.0)
    on.event("turn", model="deepseek", api_key="SECRET")
    rec = json.loads(log.read_text(encoding="utf-8").strip())
    assert rec["event"] == "turn" and rec["model"] == "deepseek"
    assert "api_key" not in rec  # secrets dropped


def test_updater_command_selection(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    assert update_command(tmp_path)[:3] == ["git", "-C", str(tmp_path)]
    plain = tmp_path / "nogit"
    plain.mkdir()
    assert "pip" in update_command(plain)
    assert isinstance(current_version(), str)
    ok, msg = update(tmp_path, run=False)
    assert ok and "would run" in msg


def test_keybindings_defaults_and_override(tmp_path: Path):
    home = tmp_path / "home"; home.mkdir()
    assert load_keybindings(cwd=tmp_path, home=home)["submit"] == DEFAULTS["submit"]
    d = tmp_path / ".clims"; d.mkdir()
    (d / "keybindings.json").write_text(json.dumps({"submit": "c-j"}), encoding="utf-8")
    assert load_keybindings(cwd=tmp_path, home=home)["submit"] == "c-j"


def test_diagnostics_loader(tmp_path: Path):
    assert load_diagnostics(tmp_path) == []
    d = tmp_path / ".clims"; d.mkdir()
    (d / "diagnostics.json").write_text(json.dumps(
        [{"file": "a.py", "line": 3, "severity": "error", "message": "bad"}]), encoding="utf-8")
    diags = load_diagnostics(tmp_path)
    assert diags[0]["file"] == "a.py"
    assert "a.py:3 [error] bad" in format_diagnostics(diags)


def test_notify_does_not_crash():
    assert notify("done") in (True, False)


def test_message_queue():
    q = MessageQueue()
    q.put("hello")
    q.put("world")
    assert q.pending() == 2
    assert q.get(timeout=1) == "hello"
    assert q.get(timeout=1) == "world"
    assert q.get(timeout=0.01) is None


def test_input_fallback_without_vim():
    # without prompt_toolkit OR vim disabled, Input is constructible and not vim
    i = Input(vim=False)
    assert i.vim is False
    assert isinstance(prompt_toolkit_available(), bool)
