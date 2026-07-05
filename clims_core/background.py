"""Background agent tasks.

Kick off an agent task in a thread, keep working, and check on it later — the
"run in background, notify when done" pattern. Thread-safe registry keyed by id.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class BackgroundTask:
    id: str
    label: str
    status: str = "running"        # running | done | error
    result: str = ""
    error: str = ""
    done_event: threading.Event = field(default_factory=threading.Event)


class BackgroundTasks:
    def __init__(self, on_complete: Callable[[BackgroundTask], None] | None = None):
        self._tasks: dict[str, BackgroundTask] = {}
        self._lock = threading.Lock()
        self._on_complete = on_complete

    def start(self, fn: Callable[[], str], label: str = "task") -> str:
        tid = "bg_" + uuid.uuid4().hex[:8]
        task = BackgroundTask(id=tid, label=label)
        with self._lock:
            self._tasks[tid] = task

        def runner():
            try:
                task.result = fn() or ""
                task.status = "done"
            except Exception as e:
                task.status = "error"
                task.error = f"{type(e).__name__}: {e}"
            finally:
                task.done_event.set()
                if self._on_complete:
                    try:
                        self._on_complete(task)
                    except Exception:
                        pass

        threading.Thread(target=runner, daemon=True).start()
        return tid

    def get(self, tid: str) -> BackgroundTask | None:
        with self._lock:
            return self._tasks.get(tid)

    def list(self) -> list[BackgroundTask]:
        with self._lock:
            return list(self._tasks.values())

    def wait(self, tid: str, timeout: float | None = None) -> BackgroundTask | None:
        task = self.get(tid)
        if task is None:
            return None
        task.done_event.wait(timeout)
        return task

    def pending(self) -> int:
        with self._lock:
            return sum(1 for t in self._tasks.values() if t.status == "running")
