"""Deeper tools: MultiEdit (atomic) + Read directory listing."""
from pathlib import Path

from clims_core.tools import MultiEditTool, ReadTool, WriteTool, tool_map, default_tools
from clims_core.tools.base import ToolContext


def test_multi_edit_applies_all(tmp_path: Path):
    ctx = ToolContext(cwd=tmp_path)
    WriteTool().run({"path": "f.py", "content": "a = 1\nb = 2\nc = 3\n"}, ctx)  # tracks read
    res = MultiEditTool().run({"path": "f.py", "edits": [
        {"old_string": "a = 1", "new_string": "a = 10"},
        {"old_string": "c = 3", "new_string": "c = 30"},
    ]}, ctx)
    assert not res.is_error
    text = (tmp_path / "f.py").read_text(encoding="utf-8")
    assert "a = 10" in text and "c = 30" in text and "b = 2" in text


def test_multi_edit_atomic_on_failure(tmp_path: Path):
    ctx = ToolContext(cwd=tmp_path)
    WriteTool().run({"path": "f.py", "content": "x = 1\n"}, ctx)
    res = MultiEditTool().run({"path": "f.py", "edits": [
        {"old_string": "x = 1", "new_string": "x = 2"},
        {"old_string": "NOT THERE", "new_string": "y"},   # fails -> nothing applied
    ]}, ctx)
    assert res.is_error
    assert (tmp_path / "f.py").read_text(encoding="utf-8") == "x = 1\n"  # unchanged


def test_multi_edit_requires_read(tmp_path: Path):
    (tmp_path / "f.py").write_text("x = 1\n", encoding="utf-8")
    res = MultiEditTool().run({"path": "f.py", "edits": [
        {"old_string": "x", "new_string": "y"}]}, ToolContext(cwd=tmp_path))
    assert res.is_error and "read" in res.content.lower()


def test_read_lists_directory(tmp_path: Path):
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    res = ReadTool().run({"path": "."}, ToolContext(cwd=tmp_path))
    assert "a.txt" in res.content and "sub/" in res.content


def test_multi_edit_in_default_tools():
    assert "multi_edit" in tool_map(default_tools())
