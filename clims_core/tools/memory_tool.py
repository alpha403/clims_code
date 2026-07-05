"""memory tool — persistent notes across sessions.

Reads/writes a sandboxed `.clims/memory/` directory under the workspace so the
agent can remember facts, decisions, and progress between runs (the "memory tool"
in Claude Code). All paths are confined to that directory.
"""
from __future__ import annotations

from pathlib import Path

from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult

MEMORY_DIR = ".clims/memory"


class MemoryTool(Tool):
    name = "memory"
    description = (
        "Persistent memory across sessions, stored in .clims/memory/. "
        "commands: list | read | write | append | delete. Use it to remember "
        "durable facts, decisions, and in-progress task state."
    )
    permission = PermissionClass.MUTATING
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "enum": ["list", "read", "write", "append", "delete"]},
            "path": {"type": "string", "description": "Relative path within memory (e.g. notes.md)."},
            "content": {"type": "string", "description": "Content for write/append."},
        },
        "required": ["command"],
    }

    def _root(self, ctx: ToolContext) -> Path:
        root = (ctx.cwd / MEMORY_DIR).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _resolve(self, root: Path, path: str) -> Path | None:
        target = (root / path).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return None  # escape attempt
        return target

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        command = input.get("command")
        root = self._root(ctx)

        if command == "list":
            files = [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()]
            return ToolResult.ok("\n".join(sorted(files)) or "(memory empty)")

        path = input.get("path")
        if not path and command != "list":
            return ToolResult.error("memory: 'path' is required")
        target = self._resolve(root, path)
        if target is None:
            return ToolResult.error("memory: path escapes the memory directory")

        if command == "read":
            if not target.is_file():
                return ToolResult.error(f"memory: not found: {path}")
            return ToolResult.ok(target.read_text(encoding="utf-8", errors="replace"))
        if command in ("write", "append"):
            content = input.get("content", "")
            target.parent.mkdir(parents=True, exist_ok=True)
            if command == "append" and target.exists():
                content = target.read_text(encoding="utf-8") + content
            target.write_text(content, encoding="utf-8")
            return ToolResult.ok(f"memory: {command} {path} ({len(content)} bytes)")
        if command == "delete":
            if target.is_file():
                target.unlink()
                return ToolResult.ok(f"memory: deleted {path}")
            return ToolResult.error(f"memory: not found: {path}")
        return ToolResult.error(f"memory: unknown command {command}")
