"""Recurring / scheduled tasks.

Persisted interval schedules ("run this prompt every N seconds/minutes"). The
store + due-logic are pure and testable; a thin background thread runs due
schedules via an injected runner while the CLI is open (or a daemon process).
"""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable


@dataclass
class Schedule:
    id: str
    prompt: str
    interval_seconds: int
    last_run: float = 0.0
    enabled: bool = True
    label: str = ""


class Scheduler:
    def __init__(self, path: Path | None = None):
        self.path = path or (Path.home() / ".clims" / "schedules.json")
        self.schedules: dict[str, Schedule] = {}
        self._lock = threading.Lock()
        self._load()

    # ---- persistence ----
    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for d in data.get("schedules", []):
            try:
                s = Schedule(**d)
                self.schedules[s.id] = s
            except TypeError:
                continue

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps({"schedules": [asdict(s) for s in self.schedules.values()]}, indent=2),
                encoding="utf-8")
        except OSError:
            pass

    # ---- CRUD ----
    def add(self, prompt: str, interval_seconds: int, label: str = "") -> str:
        sid = "sch_" + uuid.uuid4().hex[:8]
        with self._lock:
            self.schedules[sid] = Schedule(id=sid, prompt=prompt,
                                           interval_seconds=max(1, int(interval_seconds)),
                                           label=label or prompt[:40])
            self._save()
        return sid

    def remove(self, sid: str) -> bool:
        with self._lock:
            existed = self.schedules.pop(sid, None) is not None
            if existed:
                self._save()
            return existed

    def set_enabled(self, sid: str, enabled: bool) -> bool:
        with self._lock:
            s = self.schedules.get(sid)
            if not s:
                return False
            s.enabled = enabled
            self._save()
            return True

    def list(self) -> list[Schedule]:
        with self._lock:
            return list(self.schedules.values())

    # ---- scheduling logic (testable) ----
    def due(self, now: float) -> list[Schedule]:
        with self._lock:
            return [s for s in self.schedules.values()
                    if s.enabled and (now - s.last_run) >= s.interval_seconds]

    def mark_run(self, sid: str, now: float):
        with self._lock:
            s = self.schedules.get(sid)
            if s:
                s.last_run = now
                self._save()


class SchedulerLoop:
    """Background thread that runs due schedules via `runner(prompt)`."""
    def __init__(self, scheduler: Scheduler, runner: Callable[[str], None],
                 clock: Callable[[], float], tick_seconds: float = 30.0):
        self.scheduler = scheduler
        self.runner = runner
        self.clock = clock
        self.tick = tick_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def run_once(self):
        now = self.clock()
        for s in self.scheduler.due(now):
            self.scheduler.mark_run(s.id, now)
            try:
                self.runner(s.prompt)
            except Exception:
                pass

    def start(self):
        if self._thread:
            return

        def loop():
            while not self._stop.wait(self.tick):
                self.run_once()

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
