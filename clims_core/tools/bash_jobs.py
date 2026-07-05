"""bash_output + kill_shell — observe and stop background bash jobs.

Background jobs (started by bash with run_in_background) stream their combined
output to a temp file; these tools read that file and manage the process.
"""
from __future__ import annotations

from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult


def _job(ctx: ToolContext, job_id: str):
    job = ctx.jobs.get(job_id)
    if not isinstance(job, dict) or "proc" not in job:
        return None
    return job


class BashOutputTool(Tool):
    name = "bash_output"
    description = "Read the current output and status of a background bash job by id."
    permission = PermissionClass.READ_ONLY
    input_schema = {
        "type": "object",
        "properties": {"job_id": {"type": "string"}},
        "required": ["job_id"],
    }

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        job_id = input.get("job_id")
        job = _job(ctx, job_id)
        if job is None:
            return ToolResult.error(f"bash_output: unknown job {job_id}")
        proc = job["proc"]
        rc = proc.poll()
        status = "running" if rc is None else f"exited (code {rc})"
        try:
            with open(job["outfile"], "r", encoding="utf-8", errors="replace") as f:
                out = f.read()
        except OSError as e:
            out = f"(could not read output: {e})"
        return ToolResult.ok(f"[{status}]\n{out.rstrip() or '(no output yet)'}")


class KillShellTool(Tool):
    name = "kill_shell"
    description = "Terminate a running background bash job by id."
    permission = PermissionClass.EXEC
    input_schema = {
        "type": "object",
        "properties": {"job_id": {"type": "string"}},
        "required": ["job_id"],
    }

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        job_id = input.get("job_id")
        job = _job(ctx, job_id)
        if job is None:
            return ToolResult.error(f"kill_shell: unknown job {job_id}")
        proc = job["proc"]
        if proc.poll() is not None:
            return ToolResult.ok(f"job {job_id} already exited (code {proc.returncode})")
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        except Exception as e:
            return ToolResult.error(f"kill_shell: {e}")
        try:
            job["fh"].close()
        except Exception:
            pass
        return ToolResult.ok(f"terminated job {job_id}")
