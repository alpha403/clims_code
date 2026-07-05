"""Auto-update for the self-hosted CLI.

`current_version()` reads the installed version; `update()` runs the appropriate
upgrade (pip for an installed package, `git pull` inside a checkout). The actual
network operation is environment-dependent; the mechanism is provided and tested
for version detection + command selection.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from clims_core import __version__


def current_version() -> str:
    return __version__


def update_command(repo_root: Path | None = None) -> list[str]:
    """Choose the upgrade command: git pull if in a checkout, else pip upgrade."""
    root = repo_root or Path(__file__).resolve().parent.parent
    if (root / ".git").exists():
        return ["git", "-C", str(root), "pull", "--ff-only"]
    return [sys.executable, "-m", "pip", "install", "-U", "clims_code"]


def update(repo_root: Path | None = None, run: bool = True) -> tuple[bool, str]:
    cmd = update_command(repo_root)
    if not run:
        return True, "would run: " + " ".join(cmd)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except Exception as e:
        return False, f"update failed: {e}"
    ok = r.returncode == 0
    return ok, (r.stdout or r.stderr or "").strip()[-500:]
