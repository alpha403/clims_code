"""write tool — create or overwrite a text file."""
from __future__ import annotations

from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult


class WriteTool(Tool):
    name = "write"
    description = (
        "Write a UTF-8 text file, creating parent directories as needed. "
        "Overwrites if the file exists."
    )
    permission = PermissionClass.MUTATING
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute or cwd-relative file path."},
            "content": {"type": "string", "description": "Full file content to write."},
        },
        "required": ["path", "content"],
    }

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        path = input.get("path")
        if not path:
            return ToolResult.error("write: 'path' is required")
        content = input.get("content")
        if content is None:
            return ToolResult.error("write: 'content' is required")
        target = ctx.resolve(path)
        existed = target.exists()
        if existed and ctx.read_state(target) == "unread":
            # graceful: show the current content and mark it read so the immediate
            # retry overwrites — never dead-end the agent on its own scratch files.
            try:
                current = target.read_text(encoding="utf-8", errors="replace")
            except OSError:
                current = ""
            ctx.mark_read(target)
            preview = current if len(current) <= 2000 else current[:2000] + "\n…[truncated]"
            return ToolResult.error(
                f"write: {target.name} already exists — current content shown below. Review it, "
                f"then call write again to OVERWRITE (now allowed), or use `edit` for a targeted "
                f"change, or pick a different filename.\n--- current content of {target.name} ---\n"
                f"{preview}")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as e:
            return ToolResult.error(f"write: {e}")
        ctx.mark_read(target)  # track our own write
        verb = "Overwrote" if existed else "Created"
        n = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        from clims_core.tools.syntax_check import warn_suffix
        warn = warn_suffix(str(target), content)  # auto syntax check on code files
        return ToolResult.ok(f"{verb} {target} ({n} lines, {len(content)} bytes){warn}")
