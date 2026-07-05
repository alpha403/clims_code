"""Tool runtime — dispatch a tool call through the permission gate and execute it.

Used by the agent loop. Emits agent-level StreamEvents (permission_request,
tool_result) through the provided `on_event` sink so the CLI/server can render
tool activity in the same stream as model text.
"""
from __future__ import annotations

from typing import Callable

from clims_core.agent.message import ToolUseBlock, ToolResultBlock
from clims_core.permissions.policy import PermissionPolicy, Decision
from clims_core.providers.base import StreamEvent
from clims_core.tools.base import Tool, ToolContext, ToolResult

# (tool_name, tool_input, match_target) -> approved?
ApprovalFn = Callable[[str, dict, str], bool]
EventSink = Callable[[StreamEvent], None]


class ToolRuntime:
    def __init__(
        self,
        tools: dict[str, Tool],
        policy: PermissionPolicy,
        ctx: ToolContext,
        approve: ApprovalFn | None = None,
        hooks=None,
        path_guard=None,
    ):
        self.tools = tools
        self.policy = policy
        self.ctx = ctx
        self.approve = approve
        self.hooks = hooks  # optional HookRunner
        self.path_guard = path_guard  # optional PathGuard

    def execute(self, call: ToolUseBlock, on_event: EventSink | None = None) -> ToolResultBlock:
        emit = on_event or (lambda e: None)
        tool = self.tools.get(call.name)
        if tool is None:
            return self._fail(call, emit, f"unknown tool: {call.name}")

        # path safety: workspace boundary + .clims-ignore (file tools only)
        if self.path_guard is not None and "path" in call.input:
            reason = self.path_guard.check(str(call.input.get("path", "")), self.ctx.cwd)
            if reason:
                return self._fail(call, emit, f"blocked: {reason}")

        decision = self.policy.decide(call.name, tool.permission, call.input)
        if decision == Decision.DENY:
            return self._fail(call, emit, f"denied by policy: {call.name}")
        if decision == Decision.ASK:
            target = self.policy.match_string(call.name, call.input)
            if self.hooks and self.hooks.has("Notification"):
                self.hooks.run_event("Notification",
                                     {"tool_name": call.name, "type": "permission_request"})
            emit(StreamEvent.permission(call.id, call.name, call.input))
            approved = bool(self.approve and self.approve(call.name, call.input, target))
            if not approved:
                return self._fail(call, emit, f"user denied: {call.name}")

        # PreToolUse hook — may block the call
        if self.hooks and self.hooks.has("PreToolUse"):
            outcome = self.hooks.run_event(
                "PreToolUse", {"tool_name": call.name, "tool_input": call.input})
            if outcome.blocked:
                return self._fail(call, emit, f"blocked by PreToolUse hook: {outcome.reason}")

        try:
            result: ToolResult = tool.run(call.input, self.ctx)
        except Exception as e:  # tools must not crash the loop
            result = ToolResult.error(f"{call.name} raised {type(e).__name__}: {e}")

        # PostToolUse hook — observe/annotate (cannot un-run, but can add context)
        if self.hooks and self.hooks.has("PostToolUse"):
            post = self.hooks.run_event("PostToolUse", {
                "tool_name": call.name, "tool_input": call.input,
                "tool_response": result.content, "is_error": result.is_error})
            if post.context:
                result = ToolResult(content=result.content + post.context,
                                    is_error=result.is_error)

        emit(StreamEvent.tool_done(call.id, call.name, result.content, result.is_error))
        return ToolResultBlock(
            tool_use_id=call.id,
            content=result.content,
            is_error=result.is_error,
            images=getattr(result, "images", []) or [],
        )

    def _fail(self, call: ToolUseBlock, emit: EventSink, msg: str) -> ToolResultBlock:
        emit(StreamEvent.tool_done(call.id, call.name, msg, True))
        return ToolResultBlock(tool_use_id=call.id, content=msg, is_error=True)
