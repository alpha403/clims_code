"""multi_edit tool — apply several exact-string edits to one file atomically.

All edits are validated and applied in order to an in-memory copy; the file is
written once. If ANY edit fails (not found / ambiguous), nothing is written.
Honors read-before-edit + stale detection (same as edit).
"""
from __future__ import annotations

from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult
from clims_core.tools.edit import _compact_diff


class MultiEditTool(Tool):
    name = "multi_edit"
    description = (
        "Apply multiple exact-string edits to a single file in one atomic operation. "
        "Edits apply top-to-bottom; if any one fails (string not found, or not unique "
        "without replace_all), NONE are applied. Read the file first."
    )
    permission = PermissionClass.MUTATING
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "edits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                        "replace_all": {"type": "boolean"},
                    },
                    "required": ["old_string", "new_string"],
                },
            },
        },
        "required": ["path", "edits"],
    }

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        path = input.get("path")
        edits = input.get("edits")
        if not path or not isinstance(edits, list) or not edits:
            return ToolResult.error("multi_edit: 'path' and a non-empty 'edits' list are required")
        target = ctx.resolve(path)
        if not target.exists():
            return ToolResult.error(f"multi_edit: file not found: {target}")
        state = ctx.read_state(target)
        if state == "unread":
            return ToolResult.error(f"multi_edit: read {target.name} first before editing.")
        if state == "stale":
            return ToolResult.error(f"multi_edit: {target.name} changed on disk — read it again first.")
        try:
            original = target.read_text(encoding="utf-8")
        except OSError as e:
            return ToolResult.error(f"multi_edit: {e}")

        text = original
        for i, e in enumerate(edits, 1):
            old, new = e.get("old_string"), e.get("new_string")
            if old is None or new is None:
                return ToolResult.error(f"multi_edit: edit {i} missing old_string/new_string")
            count = text.count(old)
            if count == 0:
                return ToolResult.error(f"multi_edit: edit {i} old_string not found (no edits applied)")
            if count > 1 and not e.get("replace_all"):
                return ToolResult.error(
                    f"multi_edit: edit {i} old_string not unique ({count}×); "
                    f"add context or replace_all (no edits applied)")
            text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)

        if text == original:
            return ToolResult.error("multi_edit: edits produced no change")
        try:
            target.write_text(text, encoding="utf-8")
        except OSError as e:
            return ToolResult.error(f"multi_edit: {e}")
        ctx.mark_read(target)
        diff = _compact_diff(original, text, target.name)
        from clims_core.tools.syntax_check import warn_suffix
        warn = warn_suffix(str(target), text)  # auto syntax check after the edits
        msg = f"Applied {len(edits)} edits to {target}."
        return ToolResult.ok((f"{msg}\n{diff}" if diff else msg) + warn)
