"""Windows Unix-command shims (python3/head/tail/cat/wc/which/grep/touch)."""
import os
from pathlib import Path

import pytest

from clims_core.tools import BashTool
from clims_core.tools.base import ToolContext
from clims_core.tools.winshims import ensure_shims, shim_env

win_only = pytest.mark.skipif(os.name != "nt", reason="Windows shims")


@win_only
def test_shims_created():
    d = ensure_shims()
    assert d is not None
    for name in ("python3.bat", "head.bat", "tail.bat", "cat.bat", "grep.bat", "clims_shims.py"):
        assert (d / name).exists()


@win_only
def test_shim_env_prepends_path():
    env = shim_env({"PATH": "C:\\existing"})
    assert env["PATH"].startswith(str(ensure_shims()))  # prepended, beats MS-store python3


@win_only
def test_unix_commands_work(tmp_path: Path):
    (tmp_path / "f.txt").write_text("a\nb\nc\nd\ne\n", encoding="utf-8")
    ctx = ToolContext(cwd=tmp_path)
    bash = BashTool()

    assert not bash.run({"command": "python3 --version"}, ctx).is_error
    assert "a" in bash.run({"command": "type f.txt | head -2"}, ctx).content
    assert "e" in bash.run({"command": "cat f.txt | tail -1"}, ctx).content
    assert "5" in bash.run({"command": "wc -l f.txt"}, ctx).content
    # grep finds a line
    g = bash.run({"command": "cat f.txt | grep c"}, ctx)
    assert "c" in g.content and not g.is_error
    # touch creates a file
    bash.run({"command": "touch made.txt"}, ctx)
    assert (tmp_path / "made.txt").exists()


def test_shim_env_noop_off_windows():
    # on non-Windows this is essentially a passthrough; just must not raise
    env = shim_env({"PATH": "/usr/bin"})
    assert "PATH" in env
