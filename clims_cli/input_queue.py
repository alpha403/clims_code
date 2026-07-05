"""Type-ahead message queue (queued messages).

A background daemon thread reads stdin lines into a thread-safe queue so the user
can type the next message(s) while the agent is still working. The main loop pulls
from the queue. Opt-in via CLIMS_QUEUE=1; the queue class itself is dependency-free
and unit-tested.
"""
from __future__ import annotations

import queue as _queue
import sys
import threading


class MessageQueue:
    def __init__(self):
        self._q: "_queue.Queue[str]" = _queue.Queue()
        self._reader: threading.Thread | None = None
        self._stop = threading.Event()

    def put(self, line: str) -> None:
        self._q.put(line)

    def get(self, timeout: float | None = None) -> str | None:
        try:
            return self._q.get(timeout=timeout)
        except _queue.Empty:
            return None

    def pending(self) -> int:
        return self._q.qsize()

    def start_stdin_reader(self) -> None:
        if self._reader is not None:
            return

        def _read():
            while not self._stop.is_set():
                try:
                    line = sys.stdin.readline()
                except Exception:
                    break
                if line == "":  # EOF
                    self._q.put("/exit")
                    break
                self._q.put(line.rstrip("\n"))

        self._reader = threading.Thread(target=_read, daemon=True)
        self._reader.start()

    def stop(self) -> None:
        self._stop.set()
