# 07 — Permissions & Settings

A sellable agent that runs shell commands and writes files lives or dies on its permission model. Treated as a **core feature**, not polish.

## Modes (parity with Claude Code)

| Mode | Behavior |
|------|----------|
| `default` (ask) | prompt before any MUTATING/EXEC/NETWORK tool |
| `acceptEdits` | auto-allow file edits/writes; still ask for EXEC |
| `plan` | read-only; agent may inspect & propose but not mutate/exec |
| `bypass` | allow everything (explicit, dangerous; for trusted automation) |

Mode is set per-session and can be changed live (CLI: shift+tab cycles auto-accept; API: `permission_mode` field).

## Rules

Fine-grained allow/deny/ask, evaluated before the mode default:

```
allow:  ["Read(*)", "Glob(*)", "Bash(npm run test*)", "mcp:github:*"]
ask:    ["Bash(*)", "Write(*)"]
deny:   ["Bash(rm -rf *)", "Read(./secrets/**)"]
```

- Pattern matches on tool name + argument shape (command string, path glob).
- `deny` wins over `allow` wins over `ask` wins over mode default.
- Applies equally to built-in and MCP tools.

## Decision flow

```
tool call
  → match deny rules?      → DENY
  → match allow rules?     → ALLOW
  → match ask rules?       → ASK (prompt / permission_request event)
  → fall back to mode + tool PermissionClass
```

## Settings hierarchy (parity)

Lowest → highest precedence (higher overrides lower):

```
1. enterprise/managed policy   (machine-wide, locked)
2. user settings               ~/.clims/settings.json
3. project settings            ./.clims/settings.json
4. local project settings      ./.clims/settings.local.json  (gitignored)
```

Settings cover: permission rules, default model/provider, hooks, MCP servers, env, telemetry opt-in, status line, keybindings.

## Safety extras

- `.clims-ignore` — paths the agent must not read/edit.
- Per-directory trust / `add-dir` — explicit grant to operate in a directory.
- Sandbox (Phase 6) — confine EXEC/file tools (OS sandbox / container) for the self-hosted product.
- Secret redaction in logs/transcripts; **BYOK keys never persisted**.
