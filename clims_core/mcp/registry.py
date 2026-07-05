"""MCP server registry — resolve a server by NAME to a connection spec.

So a user can say "connect github with <token>" and the agent resolves the right
launch command + the env var the token belongs in, instead of needing the full
command/URL. Specs are best-effort canonical (the MCP ecosystem moves fast); they
are editable, and `resolve()` returns None for unknown names so the caller can ask
for details or web-search them.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MCPServerSpec:
    name: str
    transport: str = "stdio"           # "stdio" | "http"
    command: str | None = None
    args: list = field(default_factory=list)
    url: str | None = None
    secret_env: str | None = None      # env var the provided secret maps to
    secret_as_arg: bool = False        # secret is appended to args (e.g. DB connection string)
    needs: str | None = None           # human note: a required positional (path, etc.)
    oauth: bool = False                # needs an OAuth flow, not a simple token
    description: str = ""


def _npx(pkg: str, *args) -> tuple[str, list]:
    return "npx", ["-y", pkg, *args]


_FS_CMD, _FS_ARGS = _npx("@modelcontextprotocol/server-filesystem")
_GH_CMD, _GH_ARGS = _npx("@modelcontextprotocol/server-github")
_GL_CMD, _GL_ARGS = _npx("@modelcontextprotocol/server-gitlab")
_SLACK_CMD, _SLACK_ARGS = _npx("@modelcontextprotocol/server-slack")
_BRAVE_CMD, _BRAVE_ARGS = _npx("@modelcontextprotocol/server-brave-search")
_GMAPS_CMD, _GMAPS_ARGS = _npx("@modelcontextprotocol/server-google-maps")
_PG_CMD, _PG_ARGS = _npx("@modelcontextprotocol/server-postgres")
_PUP_CMD, _PUP_ARGS = _npx("@modelcontextprotocol/server-puppeteer")
_MEM_CMD, _MEM_ARGS = _npx("@modelcontextprotocol/server-memory")
_EVR_CMD, _EVR_ARGS = _npx("@modelcontextprotocol/server-everything")
_GDRIVE_CMD, _GDRIVE_ARGS = _npx("@modelcontextprotocol/server-gdrive")
_SENTRY_CMD, _SENTRY_ARGS = _npx("@modelcontextprotocol/server-sentry")

MCP_SERVERS: dict[str, MCPServerSpec] = {
    "filesystem": MCPServerSpec("filesystem", command=_FS_CMD, args=_FS_ARGS,
                                needs="an allowed directory path (pass as an extra arg)",
                                description="read/write files in an allowed directory"),
    "github": MCPServerSpec("github", command=_GH_CMD, args=_GH_ARGS,
                            secret_env="GITHUB_PERSONAL_ACCESS_TOKEN",
                            description="GitHub repos, issues, PRs"),
    "gitlab": MCPServerSpec("gitlab", command=_GL_CMD, args=_GL_ARGS,
                            secret_env="GITLAB_PERSONAL_ACCESS_TOKEN",
                            description="GitLab projects/issues"),
    "slack": MCPServerSpec("slack", command=_SLACK_CMD, args=_SLACK_ARGS,
                           secret_env="SLACK_BOT_TOKEN",
                           needs="also set SLACK_TEAM_ID in env",
                           description="Slack channels/messages"),
    "brave-search": MCPServerSpec("brave-search", command=_BRAVE_CMD, args=_BRAVE_ARGS,
                                  secret_env="BRAVE_API_KEY",
                                  description="Brave web search"),
    "google-maps": MCPServerSpec("google-maps", command=_GMAPS_CMD, args=_GMAPS_ARGS,
                                 secret_env="GOOGLE_MAPS_API_KEY",
                                 description="Google Maps places/directions"),
    "postgres": MCPServerSpec("postgres", command=_PG_CMD, args=_PG_ARGS,
                              secret_as_arg=True,
                              needs="the secret is the full postgres connection string",
                              description="read-only Postgres queries"),
    "puppeteer": MCPServerSpec("puppeteer", command=_PUP_CMD, args=_PUP_ARGS,
                               description="headless browser automation/screenshots"),
    "memory": MCPServerSpec("memory", command=_MEM_CMD, args=_MEM_ARGS,
                            description="a knowledge-graph memory store"),
    "everything": MCPServerSpec("everything", command=_EVR_CMD, args=_EVR_ARGS,
                                description="MCP reference/test server"),
    "gdrive": MCPServerSpec("gdrive", command=_GDRIVE_CMD, args=_GDRIVE_ARGS, oauth=True,
                            description="Google Drive (needs OAuth, not a simple token)"),
    "sentry": MCPServerSpec("sentry", command=_SENTRY_CMD, args=_SENTRY_ARGS,
                            secret_env="SENTRY_AUTH_TOKEN",
                            description="Sentry issues"),
}
# aliases
MCP_SERVERS["fs"] = MCP_SERVERS["filesystem"]
MCP_SERVERS["brave"] = MCP_SERVERS["brave-search"]
MCP_SERVERS["browser"] = MCP_SERVERS["puppeteer"]


def known_servers() -> list[str]:
    # de-dup aliases that point to the same spec name
    return sorted({s.name for s in MCP_SERVERS.values()})


def get_spec(name: str) -> MCPServerSpec | None:
    return MCP_SERVERS.get((name or "").lower().strip())


def resolve(name: str, secret: str | None = None,
            extra_args: list | None = None) -> dict | None:
    """Return a connection conf dict for `name`, routing `secret` to the right place
    (env var, appended arg, or HTTP token). None if the server is unknown."""
    spec = get_spec(name)
    if spec is None:
        return None
    args = list(spec.args) + list(extra_args or [])
    if spec.transport == "http":
        conf: dict = {"url": spec.url}
        if secret and not spec.oauth:
            conf["token"] = secret
        return conf
    conf = {"command": spec.command}
    if spec.secret_as_arg and secret:
        args = args + [secret]
    elif secret and not spec.secret_env and spec.needs and not extra_args:
        # server needs a positional (e.g. a filesystem path) and the value arrived
        # via `secret` — route it to args so it actually takes effect.
        args = args + [secret]
    conf["args"] = args
    if spec.secret_env and secret:
        conf["env"] = {spec.secret_env: secret}
    return conf


def describe(name: str) -> str:
    spec = get_spec(name)
    if spec is None:
        return f"'{name}' is not in the registry. Known: {', '.join(known_servers())}"
    bits = [f"{spec.name}: {spec.description}"]
    if spec.oauth:
        bits.append("requires OAuth (not a simple token)")
    elif spec.secret_env:
        bits.append(f"secret -> env {spec.secret_env}")
    elif spec.secret_as_arg:
        bits.append("secret passed as an argument")
    if spec.needs:
        bits.append(f"note: {spec.needs}")
    return " · ".join(bits)
