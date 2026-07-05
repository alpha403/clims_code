"""Cancellation: agent loop stops on a cancel Event; bash kills its child; watcher."""
import sys
import threading
import time
from pathlib import Path

from clims_core.agent.loop import Agent
from clims_core.agent.message import Message
from clims_core.agent.runtime import ToolRuntime
from clims_core.permissions.policy import PermissionMode, PermissionPolicy
from clims_core.providers.base import StreamEvent
from clims_core.tools import BashTool, default_tools, tool_map
from clims_core.tools.base import ToolContext
from clims_cli.interrupt import run_interruptible

from tests.fake_provider import FakeProvider


def _agent(provider, tmp_path):
    runtime = ToolRuntime(tool_map(default_tools()),
                          PermissionPolicy(mode=PermissionMode.BYPASS),
                          ToolContext(cwd=tmp_path))
    return Agent(provider=provider, model="fake", api_key="x", runtime=runtime)


def test_precancelled_makes_no_model_call(tmp_path: Path):
    provider = FakeProvider([[StreamEvent.text_delta("hi"), StreamEvent.finished("end_turn")]])
    agent = _agent(provider, tmp_path)
    cancel = threading.Event()
    cancel.set()
    result = agent.send([Message.user("hi")], cancel=cancel)
    assert result.stop_reason == "cancelled"
    assert len(provider.calls) == 0  # never called the model


def test_cancel_stops_before_tool_execution(tmp_path: Path):
    target = tmp_path / "x.txt"
    provider = FakeProvider([[
        StreamEvent.text_delta("ok"),
        StreamEvent.tool("c1", "write", {"path": str(target), "content": "hi"}),
        StreamEvent.finished("tool_use"),
    ]])
    agent = _agent(provider, tmp_path)
    cancel = threading.Event()

    def sink(ev):
        if ev.type == "tool_use":
            cancel.set()  # user hits Esc right as the tool is proposed

    result = agent.send([Message.user("write x")], sink, cancel=cancel)
    assert result.stop_reason == "cancelled"
    assert not target.exists()  # the write tool never ran


def test_bash_killed_when_cancelled(tmp_path: Path):
    ev = threading.Event()
    ev.set()  # already cancelled
    ctx = ToolContext(cwd=tmp_path, cancel=ev)
    cmd = f'"{sys.executable}" -c "import time; time.sleep(5)"'
    t0 = time.monotonic()
    r = BashTool().run({"command": cmd, "timeout": 10}, ctx)
    elapsed = time.monotonic() - t0
    assert r.is_error and "interrupted" in r.content
    assert elapsed < 3, f"should have been killed fast, took {elapsed:.1f}s"


def test_run_interruptible_returns_result_non_interactive():
    # in tests stdin is not a TTY -> runs inline and returns the result
    res, interrupted = run_interruptible(lambda: 7, threading.Event())
    assert res == 7 and interrupted is False
