"""Tests for @-mentions and background-bash poll/kill tools."""
import time
from pathlib import Path

from clims_core.mentions import expand_mentions
from clims_core.tools import BashTool, BashOutputTool, KillShellTool
from clims_core.tools.base import ToolContext


def test_mention_expands_file(tmp_path: Path):
    (tmp_path / "notes.txt").write_text("secret plan", encoding="utf-8")
    out = expand_mentions("please read @notes.txt now", cwd=tmp_path)
    assert "secret plan" in out and "Contents of @notes.txt" in out


def test_mention_ignores_emails(tmp_path: Path):
    out = expand_mentions("email me at bob@gmail.com", cwd=tmp_path)
    assert "Contents of" not in out  # no file expansion for the email


def test_mention_missing_file_is_noop(tmp_path: Path):
    out = expand_mentions("see @nope.txt", cwd=tmp_path)
    assert out == "see @nope.txt"


def test_background_bash_poll_and_kill(tmp_path: Path):
    ctx = ToolContext(cwd=tmp_path)
    # a short job that prints then exits
    start = BashTool().run({"command": "echo hello-bg", "run_in_background": True}, ctx)
    assert not start.is_error
    job_id = start.content.split("job ")[1].split(" ")[0]
    # give it a moment to run and flush
    time.sleep(1.0)
    out = BashOutputTool().run({"job_id": job_id}, ctx)
    assert "hello-bg" in out.content
    # killing an already-exited job is handled gracefully
    killed = KillShellTool().run({"job_id": job_id}, ctx)
    assert not killed.is_error


def test_bash_output_unknown_job(tmp_path: Path):
    ctx = ToolContext(cwd=tmp_path)
    r = BashOutputTool().run({"job_id": "bash_doesnotexist"}, ctx)
    assert r.is_error
