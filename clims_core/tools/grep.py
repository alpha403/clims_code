"""grep tool — content search via regex (pure-Python, no ripgrep dependency)."""
from __future__ import annotations

import fnmatch
import os
import re
import shutil
import subprocess

from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult

MAX_MATCHES = 500
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


def _run_rg(pattern, base, file_glob, mode, case_insensitive):
    """Run ripgrep; return a ToolResult, or None to fall back to pure-Python."""
    cmd = ["rg", "--no-heading", "--color", "never"]
    if case_insensitive:
        cmd.append("-i")
    if mode == "files":
        cmd.append("-l")
    else:
        cmd += ["-n", "--max-columns", "300"]
    if file_glob:
        cmd += ["-g", file_glob]
    cmd += ["--", pattern, str(base)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    if proc.returncode not in (0, 1):  # 1 = no matches (fine); other = error -> fall back
        return None
    out = (proc.stdout or "").strip()
    if not out:
        return ToolResult.ok("(no matches)" if mode == "content" else "(no files matched)")
    lines = out.splitlines()
    if len(lines) > MAX_MATCHES:
        lines = lines[:MAX_MATCHES] + [f"… ({len(lines) - MAX_MATCHES} more)"]
    return ToolResult.ok("\n".join(lines))


class GrepTool(Tool):
    name = "grep"
    description = (
        "Search file contents with a regular expression. Optionally filter files "
        "by a glob. output_mode: 'content' (matching lines) or 'files' (paths only)."
    )
    permission = PermissionClass.READ_ONLY
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regular expression."},
            "path": {"type": "string", "description": "File or directory (default cwd)."},
            "glob": {"type": "string", "description": "Filter files, e.g. *.py"},
            "case_insensitive": {"type": "boolean"},
            "output_mode": {"type": "string", "enum": ["content", "files"]},
        },
        "required": ["pattern"],
    }

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        pattern = input.get("pattern")
        if not pattern:
            return ToolResult.error("grep: 'pattern' is required")
        flags = re.IGNORECASE if input.get("case_insensitive") else 0
        try:
            rx = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult.error(f"grep: invalid regex: {e}")

        base = ctx.resolve(input["path"]) if input.get("path") else ctx.cwd
        file_glob = input.get("glob")
        mode = input.get("output_mode", "content")

        # Prefer ripgrep when available (faster, better defaults); fall back to pure-Python.
        if shutil.which("rg"):
            rg_result = _run_rg(pattern, base, file_glob, mode,
                                bool(input.get("case_insensitive")))
            if rg_result is not None:
                return rg_result

        targets = []
        if base.is_file():
            targets = [str(base)]
        else:
            for root, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for fn in files:
                    if file_glob and not fnmatch.fnmatch(fn, file_glob):
                        continue
                    targets.append(os.path.join(root, fn))

        content_lines: list[str] = []
        matched_files: list[str] = []
        for fp in targets:
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    file_hit = False
                    for lineno, line in enumerate(f, 1):
                        if rx.search(line):
                            file_hit = True
                            if mode == "content":
                                content_lines.append(f"{fp}:{lineno}:{line.rstrip()}")
                                if len(content_lines) >= MAX_MATCHES:
                                    break
                    if file_hit:
                        matched_files.append(fp)
            except OSError:
                continue
            if mode == "content" and len(content_lines) >= MAX_MATCHES:
                break

        if mode == "files":
            if not matched_files:
                return ToolResult.ok("(no files matched)")
            return ToolResult.ok("\n".join(matched_files[:MAX_MATCHES]))
        if not content_lines:
            return ToolResult.ok("(no matches)")
        return ToolResult.ok("\n".join(content_lines))
