"""Session stores.

Two interchangeable implementations sharing the same interface:
  create() -> session_id
  get(sid) -> list[Message] | None
  set(sid, messages)
  exists(sid) -> bool
  list_ids() -> list[str]

MemorySessionStore: ephemeral (process lifetime).
SQLiteSessionStore: durable, stdlib sqlite3 (zero external deps). Stores only
conversation messages — NEVER api keys.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid

from clims_core.agent.message import Message


def _new_id() -> str:
    return "sess_" + uuid.uuid4().hex[:16]


class MemorySessionStore:
    def __init__(self):
        self._d: dict[str, list[Message]] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        sid = _new_id()
        with self._lock:
            self._d[sid] = []
        return sid

    def get(self, sid: str):
        with self._lock:
            v = self._d.get(sid)
            return list(v) if v is not None else None

    def set(self, sid: str, messages: list[Message]):
        with self._lock:
            self._d[sid] = list(messages)

    def exists(self, sid: str) -> bool:
        with self._lock:
            return sid in self._d

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._d)


class SQLiteSessionStore:
    def __init__(self, path: str = "clims_sessions.db"):
        self.path = path
        # check_same_thread=False + our own lock -> safe under ThreadingHTTPServer
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS sessions ("
            " id TEXT PRIMARY KEY, created REAL, messages TEXT)"
        )
        self._conn.commit()

    def create(self) -> str:
        sid = _new_id()
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions (id, created, messages) VALUES (?, ?, ?)",
                (sid, time.time(), "[]"),
            )
            self._conn.commit()
        return sid

    def latest_id(self) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM sessions ORDER BY rowid DESC LIMIT 1").fetchone()
        return row[0] if row else None

    def get(self, sid: str):
        with self._lock:
            row = self._conn.execute(
                "SELECT messages FROM sessions WHERE id = ?", (sid,)
            ).fetchone()
        if row is None:
            return None
        try:
            data = json.loads(row[0])
        except json.JSONDecodeError:
            return []
        return [Message.from_dict(d) for d in data]

    def set(self, sid: str, messages: list[Message]):
        # redact secrets from the PERSISTED copy only (in-memory history is untouched),
        # so credentials a user typed in chat never hit disk.
        from clims_core.redact import redact_secrets
        dicts = []
        for m in messages:
            d = m.to_dict()
            for blk in d.get("content", []):
                if isinstance(blk.get("text"), str):
                    blk["text"] = redact_secrets(blk["text"])
                if isinstance(blk.get("content"), str):
                    blk["content"] = redact_secrets(blk["content"])
            dicts.append(d)
        blob = json.dumps(dicts)
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions (id, created, messages) VALUES (?, 0.0, ?) "
                "ON CONFLICT(id) DO UPDATE SET messages = excluded.messages",
                (sid, blob),
            )
            self._conn.commit()

    def exists(self, sid: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM sessions WHERE id = ?", (sid,)
            ).fetchone()
        return row is not None

    def list_ids(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute("SELECT id FROM sessions").fetchall()
        return [r[0] for r in rows]

    def close(self):
        with self._lock:
            self._conn.close()
