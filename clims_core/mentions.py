"""@-mention expansion.

Replaces `@path/to/file` tokens in a user message with the file's contents
appended as context (Claude Code's @-mention behavior). Tokens preceded by a
word character (e.g. inside an email like name@host) are ignored.
"""
from __future__ import annotations

import re
from pathlib import Path

_MENTION_RE = re.compile(r"(?<!\w)@([\w./\\-]+)")
MAX_FILE_BYTES = 100_000
MAX_FILES = 10


def expand_mentions(text: str, cwd: Path | None = None) -> str:
    cwd = cwd or Path.cwd()
    refs = []
    for ref in _MENTION_RE.findall(text):
        if ref not in refs:
            refs.append(ref)
    appended = []
    used = 0
    for ref in refs:
        if used >= MAX_FILES:
            break
        p = Path(ref)
        target = p if p.is_absolute() else (cwd / p)
        if target.is_file():
            try:
                content = target.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if len(content) > MAX_FILE_BYTES:
                content = content[:MAX_FILE_BYTES] + "\n…[truncated]"
            appended.append(f"\n\n--- Contents of @{ref} ---\n{content}")
            used += 1
    return text + "".join(appended)
