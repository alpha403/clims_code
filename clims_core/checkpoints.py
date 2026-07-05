"""Conversation checkpoints / rewind.

Snapshots the message history after each turn so the user can `/rewind` to an
earlier point (Claude Code's rewind/checkpoint feature).
"""
from __future__ import annotations

from clims_core.agent.message import Message


class Checkpoints:
    def __init__(self):
        self._snaps: list[list[Message]] = []

    def checkpoint(self, history: list[Message]) -> None:
        self._snaps.append(list(history))

    def rewind(self, n: int = 1) -> list[Message] | None:
        """Restore the history from n checkpoints back; truncates newer snapshots.
        Returns the restored history, or None if there are no checkpoints."""
        if not self._snaps:
            return None
        idx = max(0, len(self._snaps) - 1 - n)
        target = self._snaps[idx]
        del self._snaps[idx + 1:]
        return list(target)

    def __len__(self) -> int:
        return len(self._snaps)
