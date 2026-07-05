# 06 — Built-in Tools

Built-ins are intentionally **general primitives**. Domain-specific power comes from MCP, not from baking in hundreds of tools.

## Tool interface

```python
# clims_core/tools/base.py (sketch)
class Tool(ABC):
    name: str
    description: str
    input_schema: dict          # JSON Schema -> sent to the model
    permission: PermissionClass # READ_ONLY | MUTATING | EXEC | NETWORK
    @abstractmethod
    def run(self, input: dict, ctx: ToolContext) -> ToolResult: ...
```

`ToolContext` carries: cwd, session, permission gate, hook runner, cancellation token, output streamer.

## Catalog

| Tool | Class | Notes |
|------|-------|-------|
| `read` | READ_ONLY | files, images, PDFs, notebooks; line ranges; binary detection |
| `write` | MUTATING | create/overwrite; require prior read to overwrite |
| `edit` | MUTATING | exact-string replace; unique-match enforcement; `replace_all` |
| `bash` | EXEC | shell exec; timeout; cwd; **background mode**; output streaming |
| `bash_output` | READ_ONLY | poll/stream a background job |
| `kill_shell` | EXEC | terminate background job |
| `glob` | READ_ONLY | file pattern matching, sorted by mtime |
| `grep` | READ_ONLY | ripgrep-style content search (impl: pure-Python regex walker or shell out to rg if present) |
| `web_fetch` | NETWORK | fetch URL, extract readable content/markdown |
| `web_search` | NETWORK | search; provider-pluggable (BYOK search key or MCP) |
| `todo` | READ_ONLY | task list read/write for planning (TodoWrite parity) |
| `notebook_edit` | MUTATING | edit `.ipynb` cells |
| `subagent` | — | spawn a focused child agent (see agent/subagent.py) |

## Cross-platform notes (Windows-first dev env)

- `bash` must work on Windows: prefer `cmd`/`powershell` detection or a configured shell; document the shell selection.
- Path handling normalized (`pathlib`); avoid POSIX-only assumptions.
- `grep` fallback to pure-Python when `rg`/`grep` absent.

## Permission mapping

Each tool declares a `PermissionClass`; the permission gate ([07-PERMISSIONS.md](07-PERMISSIONS.md)) decides ask/allow/deny based on mode + rules. EXEC/MUTATING/NETWORK default to **ask**; READ_ONLY defaults to **allow**.

## Hooks

PreToolUse fires before `run()` (may block/modify input); PostToolUse fires after (may post-process result). See section F of the parity matrix.
