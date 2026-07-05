from pathlib import Path

from clims_core.tools import (
    ReadTool, WriteTool, EditTool, BashTool, GlobTool, GrepTool, TodoTool,
)
from clims_core.tools.base import ToolContext


def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(cwd=tmp_path)


def test_write_read_roundtrip(tmp_path):
    c = ctx(tmp_path)
    r = WriteTool().run({"path": "a.txt", "content": "line1\nline2\n"}, c)
    assert not r.is_error
    out = ReadTool().run({"path": "a.txt"}, c)
    assert "line1" in out.content and "line2" in out.content


def test_edit_unique_and_ambiguous(tmp_path):
    c = ctx(tmp_path)
    WriteTool().run({"path": "f.txt", "content": "foo bar foo"}, c)
    # ambiguous without replace_all -> error
    amb = EditTool().run({"path": "f.txt", "old_string": "foo", "new_string": "X"}, c)
    assert amb.is_error
    # replace_all works
    allr = EditTool().run(
        {"path": "f.txt", "old_string": "foo", "new_string": "X", "replace_all": True}, c)
    assert not allr.is_error
    assert ReadTool().run({"path": "f.txt"}, c).content.count("X") == 2


def test_glob_and_grep(tmp_path):
    c = ctx(tmp_path)
    WriteTool().run({"path": "src/a.py", "content": "import os\ndef hi(): pass\n"}, c)
    WriteTool().run({"path": "src/b.py", "content": "x = 1\n"}, c)
    g = GlobTool().run({"pattern": "**/*.py"}, c)
    assert "a.py" in g.content and "b.py" in g.content
    gr = GrepTool().run({"pattern": "def hi", "output_mode": "content"}, c)
    assert "a.py" in gr.content and "def hi" in gr.content


def test_bash_runs(tmp_path):
    c = ctx(tmp_path)
    r = BashTool().run({"command": "echo clims_ok"}, c)
    assert "clims_ok" in r.content and not r.is_error


def test_todo(tmp_path):
    c = ctx(tmp_path)
    r = TodoTool().run({"items": [
        {"content": "step 1", "status": "completed"},
        {"content": "step 2", "status": "in_progress"},
    ]}, c)
    assert "1/2 done" in r.content
    assert c.jobs["__todos__"][1]["status"] == "in_progress"
