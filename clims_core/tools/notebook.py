"""notebook_edit tool — edit Jupyter .ipynb cells."""
from __future__ import annotations

import json

from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult


class NotebookEditTool(Tool):
    name = "notebook_edit"
    description = (
        "Edit a Jupyter notebook (.ipynb). edit_mode: replace (set a cell's source), "
        "insert (add a new cell before cell_number), or delete (remove a cell)."
    )
    permission = PermissionClass.MUTATING
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "cell_number": {"type": "integer", "description": "0-based cell index."},
            "new_source": {"type": "string"},
            "edit_mode": {"type": "string", "enum": ["replace", "insert", "delete"]},
            "cell_type": {"type": "string", "enum": ["code", "markdown"]},
        },
        "required": ["path", "cell_number"],
    }

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        path = input.get("path")
        target = ctx.resolve(path)
        if not target.exists():
            return ToolResult.error(f"notebook_edit: not found: {target}")
        try:
            nb = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            return ToolResult.error(f"notebook_edit: invalid notebook: {e}")
        cells = nb.setdefault("cells", [])
        n = int(input.get("cell_number", 0))
        mode = input.get("edit_mode", "replace")
        source_lines = _as_source(input.get("new_source", ""))

        if mode == "delete":
            if not 0 <= n < len(cells):
                return ToolResult.error("notebook_edit: cell_number out of range")
            cells.pop(n)
        elif mode == "insert":
            cell = _new_cell(input.get("cell_type", "code"), source_lines)
            cells.insert(min(n, len(cells)), cell)
        else:  # replace
            if not 0 <= n < len(cells):
                return ToolResult.error("notebook_edit: cell_number out of range")
            cells[n]["source"] = source_lines
            if input.get("cell_type"):
                cells[n]["cell_type"] = input["cell_type"]
        try:
            target.write_text(json.dumps(nb, indent=1), encoding="utf-8")
        except OSError as e:
            return ToolResult.error(f"notebook_edit: {e}")
        return ToolResult.ok(f"notebook_edit: {mode} cell {n} in {target.name} "
                             f"({len(cells)} cells)")


def _as_source(text: str) -> list[str]:
    if not text:
        return []
    return text.splitlines(keepends=True)


def _new_cell(cell_type: str, source: list[str]) -> dict:
    cell = {"cell_type": cell_type, "metadata": {}, "source": source}
    if cell_type == "code":
        cell["outputs"] = []
        cell["execution_count"] = None
    return cell
