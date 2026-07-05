"""Built-in tools + the tool registry."""
from __future__ import annotations

from clims_core.tools.base import Tool, ToolContext, ToolResult
from clims_core.tools.read import ReadTool
from clims_core.tools.write import WriteTool
from clims_core.tools.bash import BashTool
from clims_core.tools.bash_jobs import BashOutputTool, KillShellTool
from clims_core.tools.edit import EditTool
from clims_core.tools.multi_edit import MultiEditTool
from clims_core.tools.glob import GlobTool
from clims_core.tools.grep import GrepTool
from clims_core.tools.web_fetch import WebFetchTool
from clims_core.tools.web_search import WebSearchTool
from clims_core.tools.todo import TodoTool
from clims_core.tools.plan import ExitPlanModeTool
from clims_core.tools.memory_tool import MemoryTool
from clims_core.tools.notebook import NotebookEditTool
from clims_core.tools.generate_image import GenerateImageTool


def default_tools() -> list[Tool]:
    """The general primitive set (built-ins). Domain power comes via MCP."""
    return [
        ReadTool(), WriteTool(), EditTool(), MultiEditTool(), BashTool(),
        BashOutputTool(), KillShellTool(),
        GlobTool(), GrepTool(), WebFetchTool(), WebSearchTool(), TodoTool(),
        ExitPlanModeTool(), MemoryTool(), NotebookEditTool(),
        GenerateImageTool(),
    ]


def tool_map(tools: list[Tool]) -> dict[str, Tool]:
    return {t.name: t for t in tools}


__all__ = [
    "Tool", "ToolContext", "ToolResult",
    "ReadTool", "WriteTool", "EditTool", "MultiEditTool", "BashTool",
    "BashOutputTool", "KillShellTool",
    "GlobTool", "GrepTool", "WebFetchTool", "WebSearchTool", "TodoTool",
    "ExitPlanModeTool", "MemoryTool", "NotebookEditTool",
    "default_tools", "tool_map",
]
