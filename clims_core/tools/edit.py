"""edit tool — exact-string replacement in a file."""
from __future__ import annotations

import difflib

from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult

_MAX_DIFF_LINES = 60


def _compact_diff(old: str, new: str, path: str) -> str:
    lines = list(difflib.unified_diff(
        old.splitlines(), new.splitlines(),
        fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="", n=2))
    if len(lines) > _MAX_DIFF_LINES:
        lines = lines[:_MAX_DIFF_LINES] + [f"… (+{len(lines) - _MAX_DIFF_LINES} more diff lines)"]
    return "\n".join(lines)


class EditTool(Tool):
    name = "edit"
    description = (
        "Replace an exact string in a file. By default old_string must appear "
        "exactly once (fails otherwise). Set replace_all to replace every match."
    )
    permission = PermissionClass.MUTATING
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_string": {"type": "string", "description": "Exact text to replace."},
            "new_string": {"type": "string", "description": "Replacement text."},
            "replace_all": {"type": "boolean", "description": "Replace all occurrences."},
        },
        "required": ["path", "old_string", "new_string"],
    }

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        path = input.get("path")
        old = input.get("old_string")
        new = input.get("new_string")
        if not path or old is None or new is None:
            return ToolResult.error("edit: path, old_string, new_string are required")
        if old == new:
            return ToolResult.error("edit: old_string and new_string are identical")
        target = ctx.resolve(path)
        if not target.exists():
            return ToolResult.error(f"edit: file not found: {target}")
        state = ctx.read_state(target)
        if state == "unread":
            return ToolResult.error(
                f"edit: read {target.name} first (use the read tool) before editing it.")
        if state == "stale":
            return ToolResult.error(
                f"edit: {target.name} changed on disk since you read it — read it again first.")
        try:
            text = target.read_text(encoding="utf-8")
        except OSError as e:
            return ToolResult.error(f"edit: {e}")

        count = text.count(old)
        if count == 0:
            return ToolResult.error("edit: old_string not found in file")
        if count > 1 and not input.get("replace_all"):
            return ToolResult.error(
                f"edit: old_string is not unique ({count} matches); "
                f"provide more context or set replace_all"
            )
        new_text = text.replace(old, new) if input.get("replace_all") else text.replace(old, new, 1)
        try:
            target.write_text(new_text, encoding="utf-8")
        except OSError as e:
            return ToolResult.error(f"edit: {e}")
        ctx.mark_read(target)  # refresh tracked state after our own write
        n = count if input.get("replace_all") else 1
        diff = _compact_diff(text, new_text, target.name)
        from clims_core.tools.syntax_check import warn_suffix
        warn = warn_suffix(str(target), new_text)  # auto syntax check after the edit
        msg = f"Edited {target} ({n} replacement{'s' if n != 1 else ''})."
        body = f"{msg}\n{diff}" if diff else msg
        return ToolResult.ok(body + warn)
