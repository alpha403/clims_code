"""Notifications — terminal bell + best-effort desktop toast.

Used to alert the user when the agent finishes a long turn or needs approval.
Enabled by config/CLIMS_NOTIFY; the bell is always safe and dependency-free.
"""
from __future__ import annotations

import os
import sys


def notify(message: str = "", *, bell: bool = True) -> bool:
    enabled = os.environ.get("CLIMS_NOTIFY", "1") != "0"
    if not enabled:
        return False
    try:
        if bell:
            sys.stdout.write("\a")
        if message:
            sys.stdout.write(f"\n\033[2m🔔 {message}\033[0m\n")
        sys.stdout.flush()
    except Exception:
        return False
    return True
