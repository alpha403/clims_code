"""Smoke test that actually executes the interactive run() loop start-to-/exit.

Catches startup/runtime bugs (missing imports, NameErrors) that unit tests of the
helper functions miss because they never run the loop itself.
"""
import builtins
from pathlib import Path

import clims_cli.repl as repl


def test_run_starts_and_exits(monkeypatch, tmp_path):
    # redirect ~/.clims and cwd into the temp dir so we touch nothing real
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key-no-call")
    # feed a single '/exit' to the prompt; the loop must reach it without a model call
    monkeypatch.setattr(builtins, "input", lambda *a: "/exit")
    rc = repl.run()
    assert rc == 0


def test_run_handles_a_few_slash_commands(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy")
    seq = iter(["/help", "/tools", "/mcp", "/cost", "/doctor", "/exit"])
    monkeypatch.setattr(builtins, "input", lambda *a: next(seq))
    assert repl.run() == 0  # exercises the slash dispatch without any model call
