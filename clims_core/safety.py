"""Path safety — workspace boundary + .clims-ignore enforcement.

A sellable agent that writes files and runs commands must not be able to read or
clobber anything on the machine. PathGuard enforces two rules on file tools:

  1. Workspace boundary: file paths must resolve inside an allowed root
     (default: the working directory). Blocks `../../etc/passwd`-style escapes.
  2. .clims-ignore: gitignore-style deny globs (secrets, .env, key files, …).

Bash/exec is gated separately by the permission policy (EXEC class asks/denies).
"""
from __future__ import annotations

import fnmatch
from pathlib import Path

IGNORE_FILENAME = ".clims-ignore"
# sensible defaults even without a .clims-ignore file
DEFAULT_IGNORE = ["*.key", "*.pem", "id_rsa", ".env", ".env.*", ".git/**"]


def load_ignore(cwd: Path) -> list[str]:
    patterns = list(DEFAULT_IGNORE)
    f = cwd / IGNORE_FILENAME
    if f.is_file():
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
        except OSError:
            pass
    return patterns


def _within(target: Path, root: Path) -> bool:
    try:
        return target == root or target.is_relative_to(root)
    except AttributeError:  # < py3.9 (we target 3.10, so present)
        return str(target).startswith(str(root))


class PathGuard:
    def __init__(self, roots: list[Path] | None = None, ignore: list[str] | None = None,
                 enabled: bool = True):
        self.roots = [Path(r).resolve() for r in (roots or [Path.cwd()])]
        self.ignore = ignore if ignore is not None else []
        self.enabled = enabled

    def check(self, path: str, cwd: Path | None = None) -> str | None:
        """Return a block reason, or None if the path is allowed."""
        if not self.enabled or not path:
            return None
        cwd = cwd or self.roots[0]
        target = Path(path)
        if not target.is_absolute():
            target = cwd / target
        try:
            target = target.resolve()
        except OSError:
            target = target.absolute()

        if self.roots and not any(_within(target, r) for r in self.roots):
            return f"path is outside the allowed workspace: {target}"

        for r in self.roots:
            try:
                rel = target.relative_to(r)
            except ValueError:
                continue
            rel_posix = rel.as_posix()
            for pat in self.ignore:
                if (fnmatch.fnmatch(rel_posix, pat)
                        or fnmatch.fnmatch(target.name, pat)
                        or any(fnmatch.fnmatch(seg, pat) for seg in rel.parts)):
                    return f"path is blocked by {IGNORE_FILENAME} pattern '{pat}': {rel_posix}"
        return None
