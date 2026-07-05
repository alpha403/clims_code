"""glob tool — fast file pattern matching, sorted by modification time."""
from __future__ import annotations

import glob as _glob
import os

from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult

MAX_RESULTS = 1000


class GlobTool(Tool):
    name = "glob"
    description = (
        "Find files matching a glob pattern (supports ** for recursion), relative "
        "to a base directory. Returns paths sorted by most-recently-modified first."
    )
    permission = PermissionClass.READ_ONLY
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "e.g. **/*.py or src/*.txt"},
            "path": {"type": "string", "description": "Base directory (default: cwd)."},
        },
        "required": ["pattern"],
    }

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        pattern = input.get("pattern")
        if not pattern:
            return ToolResult.error("glob: 'pattern' is required")
        base = ctx.resolve(input["path"]) if input.get("path") else ctx.cwd
        full = str(base / pattern)
        try:
            matches = _glob.glob(full, recursive=True)
        except OSError as e:
            return ToolResult.error(f"glob: {e}")
        files = [m for m in matches if os.path.isfile(m)]
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        if not files:
            return ToolResult.ok("(no matches)")
        shown = files[:MAX_RESULTS]
        body = "\n".join(shown)
        if len(files) > MAX_RESULTS:
            body += f"\n… ({len(files) - MAX_RESULTS} more)"
        return ToolResult.ok(body)
