"""bash tool — run a shell command.

Cross-platform: uses the platform shell (cmd on Windows, /bin/sh elsewhere) via
shell=True, overridable with the CLIMS_SHELL env var. Supports an optional
timeout and a background mode (returns a job id; poll/kill land in Phase 2).
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import uuid

from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult

DEFAULT_TIMEOUT = 120  # seconds
MAX_OUTPUT = 30000     # chars returned to the model


def _safe_read(stream) -> str:
    try:
        return stream.read() or ""
    except Exception:
        return ""


class BashTool(Tool):
    name = "bash"
    description = (
        "Run a shell command and return its combined stdout/stderr. Use for builds, "
        "tests, git, file inspection, and general automation. Set run_in_background "
        "for long-running processes (returns a job id).\n"
        "IMPORTANT: there is NO stdin — interactive commands fail instead of waiting. "
        "Always use non-interactive flags (e.g. `npm create vite@latest app -- --template "
        "react` with `--yes`, `npm init -y`, `pip install -q`, `git ... --no-edit`). "
        "Each call is a fresh shell, so cwd does NOT persist — chain `cd dir && cmd` or use "
        "absolute paths within one command."
    )
    permission = PermissionClass.EXEC
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute."},
            "timeout": {"type": "integer", "description": f"Timeout in seconds (default {DEFAULT_TIMEOUT})."},
            "run_in_background": {"type": "boolean", "description": "Run detached; return a job id."},
        },
        "required": ["command"],
    }

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        command = input.get("command")
        if not command:
            return ToolResult.error("bash: 'command' is required")

        shell_exe = os.environ.get("CLIMS_SHELL")  # optional explicit shell
        popen_kwargs = dict(
            cwd=str(ctx.cwd),
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            # no stdin: an interactive command gets EOF and fails fast instead of
            # hanging forever waiting for input that can never come.
            stdin=subprocess.DEVNULL,
        )
        if shell_exe:
            popen_kwargs["executable"] = shell_exe
        if os.name == "nt":
            # make Unix reflexes (python3, head, tail, cat, grep, wc, which, touch) work
            from clims_core.tools.winshims import shim_env
            popen_kwargs["env"] = shim_env()

        if input.get("run_in_background"):
            # capture output to a temp file so bash_output can poll it
            out_fd, out_path = tempfile.mkstemp(prefix="clims_bash_", suffix=".log")
            out_file = os.fdopen(out_fd, "w")
            bg_kwargs = dict(popen_kwargs)
            bg_kwargs["stdout"] = out_file
            bg_kwargs["stderr"] = subprocess.STDOUT
            try:
                proc = subprocess.Popen(command, **bg_kwargs)
            except OSError as e:
                out_file.close()
                return ToolResult.error(f"bash: failed to start: {e}")
            job_id = f"bash_{uuid.uuid4().hex[:8]}"
            ctx.jobs[job_id] = {"proc": proc, "outfile": out_path, "fh": out_file}
            return ToolResult.ok(f"Started background job {job_id} (pid {proc.pid}). "
                                 f"Poll with bash_output, stop with kill_shell.")

        timeout = int(input.get("timeout", DEFAULT_TIMEOUT))
        try:
            proc = subprocess.Popen(command, **popen_kwargs)
        except OSError as e:
            return ToolResult.error(f"bash: {e}")

        import threading
        import time
        # drain stdout in a thread (avoids pipe-buffer deadlock) while we poll the
        # process so we can react to a cancel (Esc/Ctrl-C) or the overall timeout.
        chunks: list = []
        reader = threading.Thread(target=lambda: chunks.append(_safe_read(proc.stdout)),
                                  daemon=True)
        reader.start()
        deadline = time.monotonic() + timeout
        interrupted = timed_out = False
        try:
            while proc.poll() is None:
                if ctx.cancelled():
                    proc.kill(); interrupted = True; break
                if time.monotonic() >= deadline:
                    proc.kill(); timed_out = True; break
                time.sleep(0.08)
        except KeyboardInterrupt:
            proc.kill(); reader.join(timeout=2)
            raise
        reader.join(timeout=2)
        out = (chunks[0] if chunks else "") or ""
        if interrupted:
            return ToolResult.error("bash: interrupted by user (process killed)")
        if timed_out:
            return ToolResult.error(f"bash: command timed out after {timeout}s (killed)")
        if len(out) > MAX_OUTPUT:
            out = out[:MAX_OUTPUT] + f"\n…[truncated {len(out) - MAX_OUTPUT} chars]"
        status = f"(exit code {proc.returncode})"
        body = out.rstrip() or "(no output)"
        if proc.returncode != 0:
            return ToolResult.error(f"{body}\n{status}")
        return ToolResult.ok(f"{body}\n{status}")
