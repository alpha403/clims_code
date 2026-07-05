"""Self-configuration persistence — write the agent's own settings.

Changes go to `.clims/settings.local.json` (project-local, gitignored), which is
the highest-precedence settings layer, so a self-config change overrides the
others on the next session and is applied live this session by the config tool.
Secrets (API keys, MCP tokens) are NEVER written here — they stay in memory.
"""
from __future__ import annotations

import json
from pathlib import Path

LOCAL_NAME = "settings.local.json"


def _path(cwd: Path) -> Path:
    return cwd / ".clims" / LOCAL_NAME


def load_local(cwd: Path) -> dict:
    try:
        return json.loads(_path(cwd).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_local(cwd: Path, data: dict) -> None:
    p = _path(cwd)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def set_local(cwd: Path, key: str, value) -> dict:
    data = load_local(cwd)
    data[key] = value
    write_local(cwd, data)
    return data


def append_local_list(cwd: Path, key: str, item: str) -> list:
    data = load_local(cwd)
    lst = data.setdefault(key, [])
    if item not in lst:
        lst.append(item)
    write_local(cwd, data)
    return lst
