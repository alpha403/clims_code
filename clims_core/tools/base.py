"""Tool interface + execution context.

A Tool exposes a JSON-Schema `input_schema` to the model and a `run()` that
executes it. Each tool declares a PermissionClass so the policy can gate it
uniformly. The same interface is used to wrap MCP tools later.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from clims_core.permissions.policy import PermissionClass
from clims_core.providers.base import ToolSchema


@dataclass
class ToolResult:
    content: str
    is_error: bool = False
    images: list = field(default_factory=list)  # [{"media_type","data"=base64}] for vision

    @staticmethod
    def ok(content: str, images: list | None = None) -> "ToolResult":
        return ToolResult(content=content, is_error=False, images=images or [])

    @staticmethod
    def error(content: str) -> "ToolResult":
        return ToolResult(content=content, is_error=True)


@dataclass
class ToolContext:
    """Ambient state handed to every tool run."""
    cwd: Path = field(default_factory=Path.cwd)
    # background bash jobs: id -> handle (populated by BashTool)
    jobs: dict = field(default_factory=dict)
    # file-state tracking: absolute path -> mtime when last read (read-before-edit)
    file_reads: dict = field(default_factory=dict)
    # cooperative cancellation: a threading.Event set when the user interrupts (Esc/Ctrl-C);
    # long-running tools poll cancelled() and abort.
    cancel: object = None

    def cancelled(self) -> bool:
        return self.cancel is not None and self.cancel.is_set()

    def resolve(self, path: str) -> Path:
        p = Path(path)
        return p if p.is_absolute() else (self.cwd / p)

    # ---- read-before-edit / stale-edit detection (Claude Code parity) ----
    def mark_read(self, path: Path) -> None:
        try:
            self.file_reads[str(path.resolve())] = path.stat().st_mtime
        except OSError:
            pass

    def read_state(self, path: Path) -> str:
        """Return '', 'unread', or 'stale' for an existing file the agent may edit."""
        key = str(path.resolve())
        if key not in self.file_reads:
            return "unread"
        try:
            if path.stat().st_mtime > self.file_reads[key] + 1e-6:
                return "stale"
        except OSError:
            return ""
        return ""


class Tool(ABC):
    name: str
    description: str
    permission: PermissionClass
    input_schema: dict

    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
        )

    @abstractmethod
    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        raise NotImplementedError
