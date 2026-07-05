"""configure tool — the agent reconfigures clims_code on the user's request.

When the user says things like "allow all git commands", "stop asking before edits",
"switch to concise style", or "use deepseek-reasoner", the agent calls this tool. It
applies the change to the LIVE session where possible and persists it to
.clims/settings.local.json for next time. Never persists secrets.
"""
from __future__ import annotations

from pathlib import Path

from clims_core.permissions.policy import PermissionMode, PermissionPolicy
from clims_core.selfconfig import set_local, append_local_list, load_local
from clims_core.tools.base import Tool, ToolContext, ToolResult
from clims_core.tools.base import Tool as _T  # noqa
from clims_core.permissions.policy import PermissionClass

_RULE_ACTIONS = {"allow", "deny", "ask"}


class ConfigTool(Tool):
    name = "configure"
    description = (
        "Change clims_code's OWN configuration when the user asks (permissions, model, "
        "output style, temperature, permission mode, or connecting an MCP server). "
        "Applies live and persists to settings.local.json. Actions: allow/deny/ask (with "
        "a `pattern` like 'Bash(git *)'), set_mode (default|acceptEdits|plan|bypass), "
        "set_model, set_style (default|concise|explanatory|formal|bullet), set_temperature, "
        "add_mcp (connect a Model Context Protocol server: give `name` and either `command`"
        "+`args`(+`env` for stdio creds) or `url`(+`token` for HTTP)), show."
    )
    permission = PermissionClass.MUTATING  # config changes are sensitive -> gated
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string",
                       "enum": ["allow", "deny", "ask", "set_mode", "set_model",
                                "set_style", "set_temperature", "add_mcp", "show"]},
            "pattern": {"type": "string", "description": "rule pattern for allow/deny/ask"},
            "value": {"type": "string", "description": "value for set_* actions"},
            "name": {"type": "string",
                     "description": "MCP server name. If it's a known server (github, slack, "
                                    "postgres, filesystem, brave-search, …) just give the name "
                                    "and `secret` and it resolves automatically."},
            "secret": {"type": "string",
                       "description": "the credential for a known server (token/api key/connection "
                                      "string); routed to the right env var/arg by the registry"},
            "command": {"type": "string", "description": "stdio command (override / unknown server)"},
            "args": {"type": "array", "items": {"type": "string"}},
            "url": {"type": "string", "description": "HTTP MCP url (override / unknown server)"},
            "env": {"type": "object", "description": "env vars / stdio creds (override)"},
            "token": {"type": "string", "description": "HTTP bearer token (override)"},
        },
        "required": ["action"],
    }

    def __init__(self, policy: PermissionPolicy, cwd: Path, session: dict | None = None):
        self.policy = policy          # shared with the live runtime
        self.cwd = cwd
        self.session = session if session is not None else {}  # {"agent":...}

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        action = input.get("action")
        agent = self.session.get("agent")

        if action == "show":
            cur = {
                "permission_mode": self.policy.mode.value,
                "allow": self.policy.allow, "deny": self.policy.deny, "ask": self.policy.ask,
                "model": getattr(agent, "model", None),
                "persisted": load_local(self.cwd),
            }
            return ToolResult.ok(str(cur))

        if action in _RULE_ACTIONS:
            pattern = input.get("pattern")
            if not pattern:
                return ToolResult.error(f"configure: '{action}' needs a 'pattern'")
            getattr(self.policy, action).append(pattern)        # live
            append_local_list(self.cwd, action, pattern)        # persist
            return ToolResult.ok(f"{action} rule added live + saved: {pattern}")

        if action == "set_mode":
            val = (input.get("value") or "").strip()
            try:
                self.policy.mode = PermissionMode(val)           # live
            except ValueError:
                return ToolResult.error("configure: mode must be default|acceptEdits|plan|bypass")
            set_local(self.cwd, "permission_mode", val)          # persist
            return ToolResult.ok(f"permission mode -> {val} (live + saved)")

        if action == "set_model":
            val = (input.get("value") or "").strip()
            if not val:
                return ToolResult.error("configure: set_model needs a 'value'")
            if agent is not None:
                agent.model = val                                # live
            set_local(self.cwd, "model", val)                    # persist
            return ToolResult.ok(f"model -> {val} (live + saved)")

        if action == "set_temperature":
            try:
                t = float(input.get("value"))
            except (TypeError, ValueError):
                return ToolResult.error("configure: set_temperature needs a numeric value")
            if agent is not None:
                agent.temperature = t                            # live
            set_local(self.cwd, "temperature", t)                # persist
            return ToolResult.ok(f"temperature -> {t} (live + saved)")

        if action == "set_style":
            val = (input.get("value") or "").strip()
            from clims_core.styles import style_names
            if val not in style_names():
                return ToolResult.error(f"configure: style must be one of {style_names()}")
            set_local(self.cwd, "output_style", val)             # persist (applies next /clear or restart)
            return ToolResult.ok(f"output style -> {val} (saved; takes effect on /clear or restart)")

        if action == "add_mcp":
            return self._add_mcp(input)

        return ToolResult.error(f"configure: unknown action {action}")

    def _build_mcp_conf(self, input: dict):
        """Build the connection conf — from explicit command/url, else the registry."""
        if input.get("command") or input.get("url"):
            conf: dict = {}
            if input.get("command"):
                conf["command"] = input["command"]
                conf["args"] = input.get("args", []) or []
                if input.get("env"):
                    conf["env"] = input["env"]
            if input.get("url"):
                conf["url"] = input["url"]
                if input.get("token"):
                    conf["token"] = input["token"]
            return conf, None
        # no explicit endpoint -> resolve by name from the registry
        from clims_core.mcp.registry import resolve, get_spec, known_servers
        spec = get_spec(input.get("name", ""))
        if spec is None:
            return None, (f"'{input.get('name')}' is not a known MCP server and no command/url "
                          f"was given. Known: {', '.join(known_servers())}. Provide a command "
                          f"(stdio) or url (http), or web-search the server's connection details.")
        if spec.oauth:
            return None, (f"'{spec.name}' requires an OAuth flow, not a simple token. Provide a "
                          f"url + oauth config, or the launch command directly.")
        secret = input.get("secret") or input.get("token")
        conf = resolve(input["name"], secret=secret,
                       extra_args=input.get("extra_args") or input.get("args"))
        return conf, None

    def _add_mcp(self, input: dict) -> ToolResult:
        name = input.get("name")
        if not name:
            return ToolResult.error("configure add_mcp: 'name' is required")
        conf, err = self._build_mcp_conf(input)
        if err:
            return ToolResult.error("configure add_mcp: " + err)

        mcp_mgr = self.session.get("mcp_mgr")
        runtime = self.session.get("runtime")
        agent = self.session.get("agent")
        if mcp_mgr is None:
            from clims_core.mcp import MCPManager
            mcp_mgr = MCPManager()
            self.session["mcp_mgr"] = mcp_mgr
            if agent is not None:
                agent._mcp_mgr = mcp_mgr

        before = {t.name for t in mcp_mgr.tools()}
        try:
            mcp_mgr.connect(name, conf)
        except Exception as e:
            return ToolResult.error(f"configure add_mcp: failed to connect '{name}': {e}")

        # add the new tools to the LIVE runtime + refresh what the model sees
        new_tools = [t for t in mcp_mgr.tools() if t.name not in before]
        if runtime is not None:
            for t in new_tools:
                runtime.tools[t.name] = t
        if agent is not None and runtime is not None:
            agent.tools_schema = [t.schema() for t in runtime.tools.values()]

        # persist only the NON-secret connection info so it reconnects next session
        safe = {k: v for k, v in conf.items() if k not in ("env", "token")}
        servers = load_local(self.cwd).get("mcpServers", {})
        servers[name] = safe
        set_local(self.cwd, "mcpServers", servers)

        names = ", ".join(t.name for t in new_tools) or "(none)"
        return ToolResult.ok(
            f"Connected MCP server '{name}' — added {len(new_tools)} tool(s): {names}. "
            f"Credentials kept in memory (not saved to disk). Connection info saved for reconnect.")
