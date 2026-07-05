# 05 — MCP Client

MCP (Model Context Protocol) is the **capability multiplier** that makes clims_code good at "all digital work" without hand-writing a tool for every app. By being a solid MCP *client*, clims_code inherits the entire MCP server ecosystem (Slack, GitHub, Postgres, Gmail, Drive, browsers, filesystems, etc.).

## Transports

- **stdio** — launch a local MCP server process; JSON-RPC 2.0 over stdin/stdout.
- **HTTP / SSE** — connect to a remote MCP server endpoint; JSON-RPC over HTTP with SSE for server→client.

Both implementable with stdlib (`subprocess`, `json`, `http.py`).

## Lifecycle

```
1. Load server configs (.mcp.json equivalent + settings).
2. For each server: initialize handshake → capabilities.
3. tools/list, resources/list, prompts/list.
4. Namespace tools as  mcp:<server>:<tool>  to avoid collisions.
5. Aggregate into the tool runtime so the model sees them like built-ins.
6. On tool call → JSON-RPC tools/call → normalize result to ToolResultBlock.
```

## Config shape (sketch)

```json
{
  "mcpServers": {
    "github":   { "command": "npx", "args": ["-y","@modelcontextprotocol/server-github"],
                  "env": {"GITHUB_TOKEN":"..."} },
    "postgres": { "command": "uvx", "args": ["mcp-server-postgres","postgresql://..."] },
    "remote":   { "url": "https://example.com/mcp", "transport": "sse",
                  "oauth": true }
  }
}
```

## OAuth (remote servers)

- Support the MCP OAuth flow for remote servers requiring auth.
- Tokens stored per-server in the OS-appropriate location; refreshed as needed.
- Never logged.

## Surfacing to the model

MCP tools are presented through the same `ToolSchema` the model already understands, so native function-calling works unchanged. Permission rules (section E of parity matrix) apply to MCP tools too — e.g. `ask` before `mcp:postgres:query`.

## Also support (parity)

- MCP **resources** (read external context the server exposes).
- MCP **prompts** (server-provided prompt templates surfaced as slash commands).

## Phasing

MCP is **Phase 3** — promoted early because it is the main path to general-purpose competence.
