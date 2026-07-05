"""Batch 2: memory tool, skills loader, checkpoints, session latest_id."""
from pathlib import Path

from clims_core.checkpoints import Checkpoints
from clims_core.commands import load_skills
from clims_core.agent.message import Message
from clims_core.session.store import SQLiteSessionStore
from clims_core.tools import MemoryTool
from clims_core.tools.base import ToolContext


def test_memory_tool_write_read_list_delete(tmp_path: Path):
    ctx = ToolContext(cwd=tmp_path)
    t = MemoryTool()
    assert not t.run({"command": "write", "path": "notes.md", "content": "remember X"}, ctx).is_error
    assert "remember X" in t.run({"command": "read", "path": "notes.md"}, ctx).content
    assert "notes.md" in t.run({"command": "list"}, ctx).content
    # append
    t.run({"command": "append", "path": "notes.md", "content": " and Y"}, ctx)
    assert "and Y" in t.run({"command": "read", "path": "notes.md"}, ctx).content
    # delete
    assert not t.run({"command": "delete", "path": "notes.md"}, ctx).is_error
    assert t.run({"command": "read", "path": "notes.md"}, ctx).is_error


def test_memory_tool_sandbox_escape(tmp_path: Path):
    ctx = ToolContext(cwd=tmp_path)
    res = MemoryTool().run({"command": "write", "path": "../../escape.txt", "content": "x"}, ctx)
    assert res.is_error and "escape" in res.content.lower()


def test_skills_loader(tmp_path: Path):
    d = tmp_path / ".clims" / "skills"
    d.mkdir(parents=True)
    (d / "summarize.md").write_text(
        "---\nname: summarize\ndescription: summarize a file\n---\nSummarize $ARGUMENTS",
        encoding="utf-8")
    home = tmp_path / "home"; home.mkdir()
    skills = load_skills(cwd=tmp_path, home=home)
    assert "summarize" in skills
    assert skills["summarize"].description == "summarize a file"
    assert "Summarize" in skills["summarize"].body


def test_checkpoints_rewind():
    cp = Checkpoints()
    cp.checkpoint([Message.user("a")])
    cp.checkpoint([Message.user("a"), Message.user("b")])
    cp.checkpoint([Message.user("a"), Message.user("b"), Message.user("c")])
    restored = cp.rewind(1)
    assert [m.text() for m in restored] == ["a", "b"]
    assert len(cp) == 2  # newer snapshot truncated


def test_checkpoints_empty():
    assert Checkpoints().rewind() is None


def test_session_latest_id(tmp_path: Path):
    s = SQLiteSessionStore(str(tmp_path / "s.db"))
    a = s.create()
    b = s.create()
    assert s.latest_id() == b  # most recently created
    s.set(a, [Message.user("hi")])
    assert s.get(a)[0].text() == "hi"
    s.close()
