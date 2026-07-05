"""exit_plan_mode tool — present a plan and request to leave plan mode.

In `plan` permission mode the agent is read-only; it researches and then calls
this tool with the plan it intends to execute. The host (CLI/server) can then
ask the user to approve switching to an execution mode.
"""
from __future__ import annotations

from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult


class ExitPlanModeTool(Tool):
    name = "exit_plan_mode"
    description = (
        "Call this when you are in plan mode and have finished researching: pass the "
        "concrete step-by-step plan you intend to execute. Signals the host to request "
        "approval to switch from planning to execution."
    )
    permission = PermissionClass.READ_ONLY
    input_schema = {
        "type": "object",
        "properties": {
            "plan": {"type": "string", "description": "The step-by-step plan (markdown)."},
        },
        "required": ["plan"],
    }

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        plan = input.get("plan")
        if not plan:
            return ToolResult.error("exit_plan_mode: 'plan' is required")
        # record the latest plan on the context so the host can surface/approve it
        ctx.jobs["__plan__"] = plan
        return ToolResult.ok("Plan ready for approval:\n\n" + plan)
