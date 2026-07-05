"""todo tool — lightweight task tracking (TodoWrite parity).

Lets the agent maintain a visible task list across a long multi-step job.
State lives on the ToolContext for the session.
"""
from __future__ import annotations

from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult

VALID = {"pending", "in_progress", "completed"}


class TodoTool(Tool):
    name = "todo"
    description = (
        "Maintain a structured task list for the current job. Pass the full list "
        "each call. Each item: {content, status: pending|in_progress|completed}. "
        "Keep exactly one item in_progress while working."
    )
    permission = PermissionClass.READ_ONLY
    input_schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "status": {"type": "string", "enum": sorted(VALID)},
                    },
                    "required": ["content", "status"],
                },
            }
        },
        "required": ["items"],
    }

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        items = input.get("items")
        if not isinstance(items, list):
            return ToolResult.error("todo: 'items' must be a list")
        clean = []
        for it in items:
            status = it.get("status", "pending")
            if status not in VALID:
                status = "pending"
            clean.append({"content": str(it.get("content", "")), "status": status})
        ctx.jobs["__todos__"] = clean  # stash on context
        marks = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}
        lines = [f"{marks[i['status']]} {i['content']}" for i in clean]
        done = sum(1 for i in clean if i["status"] == "completed")
        return ToolResult.ok(f"Tasks ({done}/{len(clean)} done):\n" + "\n".join(lines))
