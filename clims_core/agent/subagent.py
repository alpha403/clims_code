"""Subagent tool — delegate a focused sub-task to a child agent.

The child runs its own agent loop with its own tools and a fresh context, then
returns its final answer as the tool result. Children do NOT get a subagent tool,
which bounds recursion. Useful for isolated/parallelizable subtasks (research a
question, perform a self-contained build, summarize a large file set).
"""
from __future__ import annotations

from typing import Callable

from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult

# spawn(task_text, agent_type) -> child's final answer text
SpawnFn = Callable[[str, "str | None"], str]


class SubagentTool(Tool):
    name = "subagent"
    description = (
        "Delegate a focused sub-task to a child agent that has its own tools and a "
        "clean context. Returns the child's final answer. Use for self-contained "
        "subtasks (research, an isolated build, summarizing many files) so the main "
        "conversation stays focused. Optionally set agent_type to use a named, "
        "file-defined agent (.clims/agents/<type>.md)."
    )
    permission = PermissionClass.READ_ONLY  # spawning is safe; child tools are gated by the child's own runtime
    input_schema = {
        "type": "object",
        "properties": {
            "task": {"type": "string",
                     "description": "A complete, self-contained description of the sub-task."},
            "agent_type": {"type": "string",
                           "description": "Optional named agent to use (from .clims/agents/)."},
        },
        "required": ["task"],
    }

    def __init__(self, spawn: SpawnFn):
        self._spawn = spawn

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        task = input.get("task") or input.get("description")
        if not task:
            return ToolResult.error("subagent: 'task' is required")
        try:
            answer = self._spawn(task, input.get("agent_type"))
        except Exception as e:
            return ToolResult.error(f"subagent failed: {type(e).__name__}: {e}")
        return ToolResult.ok(answer or "(child produced no output)")
