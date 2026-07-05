"""UX render helpers (work with or without rich)."""
from dataclasses import dataclass

from clims_cli import render


@dataclass
class _Task:
    id: str
    status: str
    label: str


def test_task_line():
    line = render.task_line(_Task("bg_1", "done", "build app"))
    assert "bg_1" in line and "done" in line and "build app" in line


def test_print_tasks_empty(capsys):
    render.print_tasks([])
    assert "no background tasks" in capsys.readouterr().out


def test_print_tasks_lists(capsys):
    render.print_tasks([_Task("bg_1", "running", "job a"), _Task("bg_2", "done", "job b")])
    out = capsys.readouterr().out
    assert "bg_1" in out and "bg_2" in out and "job a" in out


def test_panel_renders_title_and_body(capsys):
    render.panel("plan", "step 1\nstep 2")
    out = capsys.readouterr().out
    assert "plan" in out and "step 1" in out and "step 2" in out


def test_status_summary():
    assert render.status_summary(0, 0) == ""
    s = render.status_summary(2, 1)
    assert "2 bg task" in s and "1 schedule" in s


def test_tool_call_and_result_render(capsys):
    render.print_tool_call("bash", {"command": "echo hello world"})
    render.print_tool_result("first line\nsecond line\nthird", is_error=False)
    render.print_tool_result("boom failed", is_error=True)
    out = capsys.readouterr().out
    assert "bash" in out and "echo hello world" in out
    assert "first line" in out and "+2 lines" in out  # multi-line summarized
    assert "boom failed" in out


def test_arg_summary_picks_salient():
    assert "echo hi" in render._arg_summary({"command": "echo hi", "timeout": 5})
    assert "/x.py" in render._arg_summary({"path": "/x.py"})


def test_logo_prints_without_crash(capsys):
    render.print_logo(version="0.1.0")
    out = capsys.readouterr().out
    assert "general-purpose agent" in out  # tagline present, no crash


def test_status_text_format():
    s = render.status_text("deepseek", "deepseek-chat", "plan", 100, 25)
    assert "deepseek:deepseek-chat" in s and "mode=plan" in s and "100 in / 25 out" in s
