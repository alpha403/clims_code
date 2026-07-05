"""Render module + edit-diff tests (work with or without rich installed)."""
from pathlib import Path

from clims_cli import render
from clims_core.tools import EditTool
from clims_core.tools.base import ToolContext


def test_unified_diff_pure():
    d = render.unified_diff("a\nb\nc", "a\nB\nc", "f.txt")
    assert "-b" in d and "+B" in d


def test_unified_diff_empty_when_same():
    assert render.unified_diff("x\ny", "x\ny", "f") == ""


def test_supports_rich_is_bool():
    assert isinstance(render.supports_rich(), bool)


def test_render_markdown_and_status_no_crash(capsys):
    render.render_markdown("# Hello\n- a\n- b")
    render.status_line("deepseek", "deepseek-chat", "default", 10, 5)
    # spinner must enter/exit cleanly regardless of rich
    with render.spinner("working"):
        pass
    out = capsys.readouterr().out
    assert "Hello" in out  # markdown content present in either mode


def test_edit_tool_includes_diff(tmp_path: Path):
    from clims_core.tools import ReadTool
    (tmp_path / "f.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)
    ReadTool().run({"path": "f.txt"}, ctx)  # read-before-edit (now required)
    res = EditTool().run({"path": "f.txt", "old_string": "beta", "new_string": "BETA"}, ctx)
    assert not res.is_error
    assert "-beta" in res.content and "+BETA" in res.content
