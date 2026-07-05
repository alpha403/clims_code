"""IDE integration — ingest editor diagnostics.

An IDE plugin (VS Code / JetBrains) writes current diagnostics (lint/type errors)
to `.clims/diagnostics.json`; the agent reads them so it knows about problems the
editor sees. Format: a list of {file, line, severity, message} or the LSP-style
{uri, range, severity, message}.
"""
from __future__ import annotations

import json
from pathlib import Path

DIAG_FILE = ".clims/diagnostics.json"


def load_diagnostics(cwd: Path | None = None) -> list[dict]:
    cwd = cwd or Path.cwd()
    p = cwd / DIAG_FILE
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        data = data.get("diagnostics", [])
    return data if isinstance(data, list) else []


def format_diagnostics(diags: list[dict]) -> str:
    if not diags:
        return "No editor diagnostics."
    lines = []
    for d in diags[:100]:
        file = d.get("file") or d.get("uri", "?")
        line = d.get("line") or (d.get("range", {}).get("start", {}).get("line", "?"))
        sev = d.get("severity", "info")
        msg = d.get("message", "")
        lines.append(f"{file}:{line} [{sev}] {msg}")
    return "\n".join(lines)
