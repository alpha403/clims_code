"""Opt-in telemetry.

Disabled by default. When enabled (config telemetry=true or CLIMS_TELEMETRY=1),
appends anonymous JSONL events to ~/.clims/telemetry.log. No network, no PII, no
prompt/response contents — only event names, counts, durations, model ids.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


class Telemetry:
    def __init__(self, enabled: bool | None = None, path: Path | None = None,
                 clock=None):
        if enabled is None:
            enabled = os.environ.get("CLIMS_TELEMETRY") == "1"
        self.enabled = enabled
        self.path = path or (Path.home() / ".clims" / "telemetry.log")
        self._clock = clock or (lambda: 0.0)

    def event(self, name: str, **fields) -> None:
        if not self.enabled:
            return
        # never record content; drop obvious content keys defensively
        safe = {k: v for k, v in fields.items()
                if k not in ("prompt", "message", "content", "text", "api_key")}
        record = {"event": name, "ts": self._clock(), **safe}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except OSError:
            pass
