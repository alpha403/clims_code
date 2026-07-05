"""PathGuard (.clims-ignore + workspace boundary) tests, incl. runtime enforcement."""
from pathlib import Path

from clims_core.agent.message import Message, ToolUseBlock
from clims_core.agent.runtime import ToolRuntime
from clims_core.permissions.policy import PermissionMode, PermissionPolicy
from clims_core.safety import PathGuard, load_ignore
from clims_core.tools import default_tools, tool_map
from clims_core.tools.base import ToolContext


def test_guard_blocks_outside_workspace(tmp_path: Path):
    g = PathGuard(roots=[tmp_path], ignore=[])
    assert g.check("notes.txt", tmp_path) is None
    reason = g.check("../../etc/passwd", tmp_path)
    assert reason and "outside" in reason


def test_guard_blocks_ignored(tmp_path: Path):
    g = PathGuard(roots=[tmp_path], ignore=["*.env", "secrets/**"])
    assert g.check("app.py", tmp_path) is None
    assert g.check("prod.env", tmp_path) is not None
    assert g.check("secrets/key.txt", tmp_path) is not None


def test_default_ignore_blocks_dotenv(tmp_path: Path):
    g = PathGuard(roots=[tmp_path], ignore=load_ignore(tmp_path))
    assert g.check(".env", tmp_path) is not None
    assert g.check("id_rsa", tmp_path) is not None


def test_runtime_enforces_guard(tmp_path: Path):
    # write tool blocked from creating an ignored file
    (tmp_path / ".clims-ignore").write_text("forbidden.txt\n", encoding="utf-8")
    guard = PathGuard(roots=[tmp_path], ignore=load_ignore(tmp_path))
    rt = ToolRuntime(tool_map(default_tools()),
                     PermissionPolicy(mode=PermissionMode.BYPASS),
                     ToolContext(cwd=tmp_path), path_guard=guard)
    block = rt.execute(ToolUseBlock("c1", "write",
                                    {"path": "forbidden.txt", "content": "x"}))
    assert block.is_error and "blocked" in block.content
    assert not (tmp_path / "forbidden.txt").exists()
    # a normal file still works
    ok = rt.execute(ToolUseBlock("c2", "write", {"path": "ok.txt", "content": "y"}))
    assert not ok.is_error and (tmp_path / "ok.txt").exists()


def test_runtime_blocks_escape(tmp_path: Path):
    guard = PathGuard(roots=[tmp_path], ignore=[])
    rt = ToolRuntime(tool_map(default_tools()),
                     PermissionPolicy(mode=PermissionMode.BYPASS),
                     ToolContext(cwd=tmp_path), path_guard=guard)
    block = rt.execute(ToolUseBlock("c1", "read", {"path": "../../../secret"}))
    assert block.is_error and "outside" in block.content
