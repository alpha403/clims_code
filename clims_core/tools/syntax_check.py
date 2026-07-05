"""Lightweight, zero-dep syntax validation run automatically after write/edit.

Catches the most common "broken code" failure — syntax errors — the instant the
agent writes a file, and surfaces the error back in the tool result so the agent
must notice and fix it (instead of moving on as if it worked). Optionally uses the
language's own checker (node --check, etc.) when present; always safe-fails to None.
"""
from __future__ import annotations

import ast
import json
import shutil
import subprocess
from pathlib import Path


def check_syntax(path: str, content: str) -> str | None:
    """Return a one-line error string if the content has a syntax error, else None."""
    ext = Path(path).suffix.lower()
    try:
        if ext in (".py", ".pyi"):
            ast.parse(content)
        elif ext == ".json":
            json.loads(content)
        elif ext in (".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"):
            return _node_check(content, ext)
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} at line {e.lineno}"
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e.msg} at line {e.lineno}"
    except Exception as e:  # noqa: BLE001 — never let the check itself raise
        return None
    return None


def _node_check(content: str, ext: str) -> str | None:
    # only plain JS can be checked with `node --check`; TS/JSX need a compiler we
    # won't assume is installed, so skip those rather than false-positive.
    if ext not in (".js", ".mjs", ".cjs") or not shutil.which("node"):
        return None
    try:
        p = subprocess.run(["node", "--check", "-"], input=content, text=True,
                           capture_output=True, timeout=10)
        if p.returncode != 0:
            first = (p.stderr or "").strip().splitlines()
            return f"JS syntax error: {first[0] if first else 'check failed'}"
    except Exception:  # noqa: BLE001
        return None
    return None


def warn_suffix(path: str, content: str) -> str:
    """A prominent warning to append to a write/edit result, or '' if syntax is OK."""
    err = check_syntax(path, content)
    if err:
        return (f"\n\n⚠️  SYNTAX ERROR in {Path(path).name}: {err}\n"
                f"The file was written but is NOT valid — fix this now before doing "
                f"anything else.")
    return ""
