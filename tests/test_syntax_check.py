"""Auto syntax-check on write/edit surfaces broken code back to the agent."""
from pathlib import Path

from clims_core.tools import WriteTool, EditTool
from clims_core.tools.base import ToolContext
from clims_core.tools.syntax_check import check_syntax, warn_suffix


def test_check_syntax_python():
    assert check_syntax("a.py", "def f():\n    return 1\n") is None
    err = check_syntax("a.py", "def f(:\n  return 1")
    assert err and "SyntaxError" in err


def test_check_syntax_json():
    assert check_syntax("c.json", '{"a": 1}') is None
    assert "JSON" in (check_syntax("c.json", '{"a": }') or "")


def test_check_skips_unknown_ext():
    assert check_syntax("notes.md", "## not code {[") is None  # no false positives


def test_write_flags_broken_python(tmp_path: Path):
    ctx = ToolContext(cwd=tmp_path)
    r = WriteTool().run({"path": "bad.py", "content": "def oops(:\n  pass"}, ctx)
    assert not r.is_error  # the write itself succeeded
    assert "SYNTAX ERROR" in r.content  # but the agent is told it's broken
    # good code: no warning
    r2 = WriteTool().run({"path": "ok.py", "content": "x = 1\n"}, ctx)
    assert "SYNTAX ERROR" not in r2.content


def test_edit_flags_broken_result(tmp_path: Path):
    (tmp_path / "m.py").write_text("x = 1\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)
    ctx.mark_read(tmp_path / "m.py")
    # edit that breaks syntax
    r = EditTool().run({"path": "m.py", "old_string": "x = 1", "new_string": "x = ("}, ctx)
    assert "SYNTAX ERROR" in r.content


def test_warn_suffix_empty_for_valid():
    assert warn_suffix("a.py", "y = 2\n") == ""
