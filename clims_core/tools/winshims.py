"""Windows Unix-command shims.

DeepSeek (and most models) reflexively use Unix tools (python3, head, tail, cat,
grep, wc, which, touch) that don't exist in cmd.exe, so commands fail and the agent
thrashes. We generate tiny shim scripts — backed by the running Python — in a dir we
PREPEND to PATH for the bash tool. cmd.exe then resolves these names transparently
(pipes/chaining included), so the Unix reflexes just work.

Prepended (not appended) so our `python3` beats the Microsoft-Store stub that prints
"Python was not found".
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_SHIM_DIR: Path | None = None
_UNIX_CMDS = ["head", "tail", "cat", "wc", "which", "touch", "grep"]

_DISPATCH = r'''
import sys, re, shutil, os

def _lines(files):
    if files:
        for f in files:
            try:
                with open(f, "r", encoding="utf-8", errors="replace") as fh:
                    for ln in fh:
                        yield ln
            except OSError as e:
                sys.stderr.write("%s: %s\n" % (f, e))
    else:
        for ln in sys.stdin:
            yield ln

def _n(a, i):
    x = a[i]
    if x == "-n":
        return int(a[i + 1]), i + 1
    if x.startswith("-n"):
        return int(x[2:]), i
    if re.fullmatch(r"-\d+", x):
        return int(x[1:]), i
    return None, i

def head(a):
    n = 10; files = []; i = 0
    while i < len(a):
        v, i = _n(a, i)
        if v is not None: n = v
        elif not a[i].startswith("-"): files.append(a[i])
        i += 1
    c = 0
    for ln in _lines(files):
        if c >= n: break
        sys.stdout.write(ln); c += 1

def tail(a):
    n = 10; files = []; i = 0
    while i < len(a):
        v, i = _n(a, i)
        if v is not None: n = v
        elif not a[i].startswith("-"): files.append(a[i])
        i += 1
    buf = list(_lines(files))
    for ln in buf[-n:]:
        sys.stdout.write(ln)

def cat(a):
    for ln in _lines([x for x in a if not x.startswith("-")]):
        sys.stdout.write(ln)

def wc(a):
    mode = [x for x in a if x.startswith("-")]
    data = list(_lines([x for x in a if not x.startswith("-")]))
    lines = len(data); words = sum(len(x.split()) for x in data); chars = sum(len(x) for x in data)
    if "-l" in mode: print(lines)
    elif "-w" in mode: print(words)
    elif "-c" in mode: print(chars)
    else: print("%d %d %d" % (lines, words, chars))

def which(a):
    code = 1
    for name in [x for x in a if not x.startswith("-")]:
        p = shutil.which(name)
        if p: print(p); code = 0
    sys.exit(code)

def touch(a):
    for f in [x for x in a if not x.startswith("-")]:
        open(f, "a", encoding="utf-8").close(); os.utime(f, None)

def grep(a):
    flags = 0; show_n = inv = False; pat = None; files = []; i = 0
    while i < len(a):
        x = a[i]
        if x == "-e": i += 1; pat = a[i]
        elif x.startswith("-") and x != "-":
            if "i" in x: flags |= re.IGNORECASE
            if "n" in x: show_n = True
            if "v" in x: inv = True
        elif pat is None: pat = x
        else: files.append(x)
        i += 1
    if pat is None: sys.exit(2)
    rx = re.compile(pat, flags); found = False
    for idx, ln in enumerate(_lines(files), 1):
        if bool(rx.search(ln)) != inv:
            found = True
            sys.stdout.write(("%d:" % idx if show_n else "") + ln)
    sys.exit(0 if found else 1)

D = {"head": head, "tail": tail, "cat": cat, "wc": wc, "which": which, "touch": touch, "grep": grep}
if __name__ == "__main__":
    fn = D.get(sys.argv[1]) if len(sys.argv) > 1 else None
    if fn is None:
        sys.exit("clims_shims: unknown command")
    try:
        fn(sys.argv[2:])
    except BrokenPipeError:
        pass
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(str(e) + "\n"); sys.exit(1)
'''


def ensure_shims() -> Path | None:
    """Create (once per process) the shim dir and return it, or None on failure."""
    global _SHIM_DIR
    if _SHIM_DIR is not None:
        return _SHIM_DIR
    if os.name != "nt":
        return None
    try:
        d = Path(tempfile.gettempdir()) / "clims_winshims"
        d.mkdir(parents=True, exist_ok=True)
        py = sys.executable or "python"
        (d / "clims_shims.py").write_text(_DISPATCH, encoding="utf-8")
        for cmd in _UNIX_CMDS:
            (d / f"{cmd}.bat").write_text(
                f'@echo off\r\n"{py}" "%~dp0clims_shims.py" {cmd} %*\r\n', encoding="utf-8")
        # python3 -> the running python (beats the Microsoft-Store stub)
        (d / "python3.bat").write_text(f'@echo off\r\n"{py}" %*\r\n', encoding="utf-8")
        _SHIM_DIR = d
        return d
    except Exception:
        return None


def shim_env(base_env: dict | None = None) -> dict:
    """Return an env dict with the shim dir PREPENDED to PATH (Windows only)."""
    env = dict(base_env if base_env is not None else os.environ)
    d = ensure_shims()
    if d is not None:
        env["PATH"] = str(d) + os.pathsep + env.get("PATH", "")
    return env
