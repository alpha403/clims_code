"""Harness-depth: file-state tracking, ripgrep fallback, read binary/image, tokens."""
from pathlib import Path

from clims_core.agent.compaction import estimate_tokens
from clims_core.agent.message import Message
from clims_core.tools import ReadTool, EditTool, WriteTool, GrepTool
from clims_core.tools.base import ToolContext


def test_edit_requires_read_first(tmp_path: Path):
    (tmp_path / "f.txt").write_text("alpha beta", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)
    # editing without reading first -> blocked
    r = EditTool().run({"path": "f.txt", "old_string": "alpha", "new_string": "X"}, ctx)
    assert r.is_error and "read" in r.content.lower()
    # after reading, edit works
    ReadTool().run({"path": "f.txt"}, ctx)
    r2 = EditTool().run({"path": "f.txt", "old_string": "alpha", "new_string": "X"}, ctx)
    assert not r2.is_error


def test_edit_detects_stale(tmp_path: Path):
    import os, time
    p = tmp_path / "f.txt"
    p.write_text("one", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)
    ReadTool().run({"path": "f.txt"}, ctx)
    # external modification after read -> bump mtime well past the recorded read
    time.sleep(0.01)
    p.write_text("changed externally", encoding="utf-8")
    os.utime(p, (p.stat().st_atime, p.stat().st_mtime + 10))
    r = EditTool().run({"path": "f.txt", "old_string": "changed", "new_string": "X"}, ctx)
    assert r.is_error and "stale" in r.content.lower() or "again" in r.content.lower()


def test_write_overwrite_graceful(tmp_path: Path):
    (tmp_path / "f.txt").write_text("orig", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)
    # first overwrite of an unread file is blocked BUT shows the current content
    r = WriteTool().run({"path": "f.txt", "content": "new"}, ctx)
    assert r.is_error and "already exists" in r.content.lower() and "orig" in r.content
    # the block marked it read, so the immediate retry overwrites (no dead-end)
    r2 = WriteTool().run({"path": "f.txt", "content": "new"}, ctx)
    assert not r2.is_error and (tmp_path / "f.txt").read_text(encoding="utf-8") == "new"
    # a brand-new file is fine without any read
    assert not WriteTool().run({"path": "new.txt", "content": "hi"}, ctx).is_error


def test_consecutive_edits_after_write_ok(tmp_path: Path):
    ctx = ToolContext(cwd=tmp_path)
    WriteTool().run({"path": "a.py", "content": "x = 1\ny = 2\n"}, ctx)  # our write tracks it
    r = EditTool().run({"path": "a.py", "old_string": "x = 1", "new_string": "x = 10"}, ctx)
    assert not r.is_error  # no stale/unread error after our own write


def test_read_handles_binary_and_image(tmp_path: Path):
    (tmp_path / "b.bin").write_bytes(b"\x00\x01\x02binary")
    (tmp_path / "p.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    ctx = ToolContext(cwd=tmp_path)
    rb = ReadTool().run({"path": "b.bin"}, ctx)
    assert "binary file" in rb.content
    ri = ReadTool().run({"path": "p.png"}, ctx)
    # now returns the actual image (image-in-tool-result), not just a text note
    assert "image:" in ri.content.lower() and ri.images
    assert ri.images[0]["media_type"] == "image/png"


def test_grep_still_works(tmp_path: Path):
    # works whether or not ripgrep is installed (rg path or pure-python fallback)
    (tmp_path / "a.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)
    r = GrepTool().run({"pattern": "def hello", "output_mode": "content"}, ctx)
    assert "hello" in r.content and not r.is_error


def test_estimate_tokens_positive():
    msgs = [Message.user("hello world " * 100)]
    assert estimate_tokens(msgs) > 0
