from pathlib import Path

from clims_core.agent.message import Message
from clims_core.session.store import SQLiteSessionStore, MemorySessionStore


def test_memory_store_roundtrip():
    s = MemorySessionStore()
    sid = s.create()
    assert s.exists(sid)
    s.set(sid, [Message.user("hi"), Message.assistant("hello")])
    msgs = s.get(sid)
    assert len(msgs) == 2 and msgs[0].text() == "hi"
    assert s.get("nope") is None


def test_sqlite_persists_across_reopen(tmp_path: Path):
    db = str(tmp_path / "s.db")
    s1 = SQLiteSessionStore(db)
    sid = s1.create()
    s1.set(sid, [Message.user("remember me"),
                 Message.assistant("noted")])
    s1.close()

    # reopen a fresh store pointing at the same file
    s2 = SQLiteSessionStore(db)
    assert s2.exists(sid)
    msgs = s2.get(sid)
    assert [m.text() for m in msgs] == ["remember me", "noted"]
    assert sid in s2.list_ids()
    s2.close()
