"""Permission policy: modes + allow/deny/ask rules.

Decision flow (highest precedence first):
    deny rule  -> DENY
    allow rule -> ALLOW
    ask rule   -> ASK
    else       -> mode default for the tool's PermissionClass

Rules are simple glob patterns matched against a "match string" built from the
tool name and its salient argument (command for bash, path for file tools), e.g.
    "Bash(npm run test*)"   matches a bash call whose command starts "npm run test"
    "Read(*)"               matches any read
    "mcp:github:*"          matches any github MCP tool
Applies identically to built-in and MCP tools.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from enum import Enum


def _is_doc_path(path: str) -> bool:
    """A markdown doc or a memory file — writable in plan mode (it's documentation,
    not a code/project change)."""
    p = (path or "").lower().replace("\\", "/")
    return p.endswith(".md") or ".clims/memory" in p


class PermissionMode(str, Enum):
    DEFAULT = "default"        # ask before mutating/exec/network
    ACCEPT_EDITS = "acceptEdits"  # auto-allow file writes/edits; ask for exec
    PLAN = "plan"              # read-only; deny all mutation/exec/network
    BYPASS = "bypass"          # allow everything (explicit, dangerous)


class PermissionClass(str, Enum):
    READ_ONLY = "read_only"
    MUTATING = "mutating"
    EXEC = "exec"
    NETWORK = "network"


class Decision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass
class PermissionPolicy:
    mode: PermissionMode = PermissionMode.DEFAULT
    allow: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)
    ask: list[str] = field(default_factory=list)

    def match_string(self, tool_name: str, tool_input: dict) -> str:
        """Build the string rules are matched against."""
        salient = ""
        if "command" in tool_input:
            salient = str(tool_input.get("command", ""))
        elif "path" in tool_input:
            salient = str(tool_input.get("path", ""))
        elif "url" in tool_input:
            salient = str(tool_input.get("url", ""))
        elif "pattern" in tool_input:
            salient = str(tool_input.get("pattern", ""))
        return f"{tool_name}({salient})"

    def decide(self, tool_name: str, perm_class: PermissionClass, tool_input: dict) -> Decision:
        target = self.match_string(tool_name, tool_input)
        bare = f"{tool_name}(*)"

        def matches(patterns: list[str]) -> bool:
            for p in patterns:
                if fnmatch.fnmatch(target, p) or fnmatch.fnmatch(tool_name, p) or p == bare:
                    return True
            return False

        # explicit rules, in precedence order
        if matches(self.deny):
            return Decision.DENY
        if matches(self.allow):
            return Decision.ALLOW
        if matches(self.ask):
            return Decision.ASK

        # mode defaults
        if self.mode == PermissionMode.BYPASS:
            return Decision.ALLOW
        if self.mode == PermissionMode.PLAN:
            # plan mode = research + document the plan, but no CODE changes / shell.
            # Allowed: reading, web research, the memory tool, and writing markdown docs.
            if perm_class in (PermissionClass.READ_ONLY, PermissionClass.NETWORK):
                return Decision.ALLOW
            if tool_name == "memory":
                return Decision.ALLOW
            if (tool_name in ("write", "edit", "multi_edit")
                    and _is_doc_path(tool_input.get("path", ""))):
                return Decision.ALLOW
            return Decision.DENY
        if self.mode == PermissionMode.ACCEPT_EDITS:
            if perm_class in (PermissionClass.READ_ONLY, PermissionClass.MUTATING):
                return Decision.ALLOW
            return Decision.ASK
        # DEFAULT
        if perm_class == PermissionClass.READ_ONLY:
            return Decision.ALLOW
        return Decision.ASK
