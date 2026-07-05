"""Memory loader.

Assembles instruction memory the way Claude Code uses CLAUDE.md:
  - user memory:    ~/.clims/CLIMS.md
  - project memory: CLIMS.md found walking up from cwd (outermost first, so the
    nearest/most-specific file wins by appearing last)
Supports `@import <path>` lines (relative to the importing file) with cycle
protection. The assembled text is prepended to the agent system prompt.
"""
from __future__ import annotations

from pathlib import Path

MEMORY_FILENAME = "CLIMS.md"
MAX_BYTES = 100_000
MAX_PARENTS = 8


def _read_with_imports(path: Path, visited: set[Path]) -> str:
    path = path.resolve()
    if path in visited or not path.exists():
        return ""
    visited.add(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    out_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("@import "):
            ref = stripped[len("@import "):].strip()
            target = (path.parent / ref) if not Path(ref).is_absolute() else Path(ref)
            imported = _read_with_imports(target, visited)
            if imported:
                out_lines.append(imported)
        else:
            out_lines.append(line)
    return "\n".join(out_lines)


def _collect_files(cwd: Path, home: Path) -> list[Path]:
    files: list[Path] = []
    # user memory first (least specific)
    user_mem = home / ".clims" / MEMORY_FILENAME
    if user_mem.exists():
        files.append(user_mem)
    # project memory: outermost parent -> cwd (most specific last)
    chain: list[Path] = []
    cur = cwd.resolve()
    for _ in range(MAX_PARENTS):
        candidate = cur / MEMORY_FILENAME
        if candidate.exists():
            chain.append(candidate)
        if cur.parent == cur:
            break
        cur = cur.parent
    files.extend(reversed(chain))  # outermost first
    return files


MEMORY_DIR = ".clims/memory"
TRACKING_DOCS = ("PROGRESS.md", "DECISIONS.md", "ARCHITECTURE.md")


def memory_digest(cwd: Path | None = None, max_chars: int = 6000) -> str:
    """Assemble what the agent already knows: the contents of .clims/memory/ plus
    any existing project tracking docs. Injected at session start so the agent
    resumes from prior context instead of starting blind."""
    cwd = (cwd or Path.cwd())
    parts: list[str] = []

    mem_dir = cwd / MEMORY_DIR
    if mem_dir.is_dir():
        for f in sorted(mem_dir.rglob("*")):
            if f.is_file():
                try:
                    body = f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                parts.append(f"## memory/{f.relative_to(mem_dir).as_posix()}\n{body.strip()}")

    for name in TRACKING_DOCS:
        p = cwd / name
        if p.is_file():
            try:
                body = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            parts.append(f"## {name} (existing)\n{body.strip()[:2000]}")

    blob = "\n\n".join(parts)
    if len(blob) > max_chars:
        blob = blob[:max_chars] + "\n…[memory digest truncated]"
    return blob


def load_memory(cwd: Path | None = None, home: Path | None = None) -> str:
    cwd = (cwd or Path.cwd()).resolve()
    home = home or Path.home()
    visited: set[Path] = set()
    parts: list[str] = []
    for f in _collect_files(cwd, home):
        content = _read_with_imports(f, visited)
        if content.strip():
            parts.append(content.strip())
    blob = "\n\n".join(parts)
    if len(blob) > MAX_BYTES:
        blob = blob[:MAX_BYTES] + "\n…[memory truncated]"
    return blob
