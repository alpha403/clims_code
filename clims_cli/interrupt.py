"""Run a turn on a worker thread while the main thread watches for an interrupt key.

Gives Claude-Code-style "press Esc (or Ctrl-C) anytime to interrupt" — the agent
runs on a background thread; pressing Esc/Ctrl-C sets a cancel Event that the loop
and tools poll, so the current action stops promptly and we return to the prompt.
Falls back to a plain blocking call (Ctrl-C only) when no interactive console.
"""
from __future__ import annotations

import sys
import threading

try:
    import msvcrt  # Windows
    _WIN = True
except Exception:
    _WIN = False

if not _WIN:
    try:
        import select
        import termios
        import tty
        _POSIX_TTY = True
    except Exception:
        _POSIX_TTY = False


def _poll_interrupt_key_win() -> bool:
    pressed = False
    while msvcrt.kbhit():
        ch = msvcrt.getwch()
        if ch in ("\x1b", "\x03"):  # Esc or Ctrl-C
            pressed = True
    return pressed


def _poll_interrupt_key_posix() -> bool:
    dr, _, _ = select.select([sys.stdin], [], [], 0)
    if dr:
        ch = sys.stdin.read(1)
        if ch in ("\x1b", "\x03"):
            return True
    return False


def _interactive() -> bool:
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def run_interruptible(fn, cancel_event: threading.Event):
    """Run fn() on a worker thread; watch for Esc/Ctrl-C and set cancel_event.
    Returns (result, interrupted). Re-raises any non-cancel error from fn."""
    if not _interactive():
        # no key watching possible; run inline, Ctrl-C still works via KeyboardInterrupt
        try:
            return fn(), False
        except KeyboardInterrupt:
            cancel_event.set()
            return None, True

    out: dict = {}

    def worker():
        try:
            out["result"] = fn()
        except BaseException as e:  # noqa: BLE001 — surface to caller
            out["error"] = e

    # POSIX: put the terminal in cbreak so single keys read without Enter
    old_termios = None
    if not _WIN and _POSIX_TTY:
        try:
            old_termios = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        except Exception:
            old_termios = None

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    interrupted = False
    try:
        while t.is_alive():
            poll = _poll_interrupt_key_win if _WIN else (
                _poll_interrupt_key_posix if (not _WIN and _POSIX_TTY) else None)
            if poll is not None and poll():
                cancel_event.set()
                interrupted = True
                break
            t.join(0.05)
    except KeyboardInterrupt:
        cancel_event.set()
        interrupted = True
    finally:
        if old_termios is not None:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_termios)
            except Exception:
                pass

    t.join()  # let the worker wind down after cancel (loop/tools see the Event)
    if "error" in out:
        raise out["error"]
    return out.get("result"), interrupted
