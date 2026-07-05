"""Hook runner.

Config shape (Claude Code-compatible subset), under settings["hooks"]:

    {
      "PreToolUse": [
        {"matcher": "bash|write", "hooks": [{"type": "command", "command": "..."}]}
      ],
      "PostToolUse": [ ... ],
      "UserPromptSubmit": [ ... ],
      "Stop": [ ... ],
      "SessionStart": [ ... ]
    }

Each hook command receives the event payload as JSON on stdin. Control protocol:
  - exit code 0  -> allow (stdout may carry JSON with "additionalContext")
  - exit code 2  -> block (stderr/stdout text becomes the reason)
  - stdout JSON {"decision": "block"|"deny", "reason": "..."} -> block
  - stdout JSON {"additionalContext": "..."} -> injected back to the model

`matcher` is a regex matched (search) against the tool name for tool events; "*"
or "" matches everything.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HookOutcome:
    blocked: bool = False
    reason: str = ""
    context: str = ""  # additionalContext aggregated from hooks
    ran: int = 0

    @property
    def allowed(self) -> bool:
        return not self.blocked


class HookRunner:
    def __init__(self, config: dict | None, cwd: Path | None = None, timeout: int = 30):
        self.config = config or {}
        self.cwd = str(cwd or Path.cwd())
        self.timeout = timeout

    def has(self, event: str) -> bool:
        return bool(self.config.get(event))

    def run_event(self, event: str, payload: dict) -> HookOutcome:
        entries = self.config.get(event, []) or []
        outcome = HookOutcome()
        tool_name = payload.get("tool_name", "")
        full_payload = {"hook_event_name": event, **payload}
        for entry in entries:
            matcher = entry.get("matcher", "*")
            if not self._matches(matcher, tool_name, event):
                continue
            for hook in entry.get("hooks", []):
                if hook.get("type") != "command":
                    continue
                command = hook.get("command", "")
                if not command:
                    continue
                self._run_one(command, full_payload, outcome)
                if outcome.blocked:
                    return outcome
        return outcome

    # ---- internals ----
    def _matches(self, matcher: str, tool_name: str, event: str) -> bool:
        if matcher in ("", "*"):
            return True
        # tool events match on tool name; non-tool events: matcher must be * to apply
        target = tool_name or event
        try:
            return re.search(matcher, target) is not None
        except re.error:
            return matcher == target

    def _run_one(self, command: str, payload: dict, outcome: HookOutcome):
        try:
            proc = subprocess.run(
                command, shell=True, cwd=self.cwd,
                input=json.dumps(payload), text=True,
                capture_output=True, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            outcome.ran += 1
            return  # a slow hook does not block by default
        except OSError:
            outcome.ran += 1
            return
        outcome.ran += 1
        stdout = (proc.stdout or "").strip()
        # JSON control output?
        parsed = None
        if stdout.startswith("{"):
            try:
                parsed = json.loads(stdout)
            except json.JSONDecodeError:
                parsed = None
        if parsed:
            decision = str(parsed.get("decision", "")).lower()
            if decision in ("block", "deny"):
                outcome.blocked = True
                outcome.reason = parsed.get("reason", "blocked by hook")
                return
            if parsed.get("additionalContext"):
                outcome.context += ("\n" + str(parsed["additionalContext"]))
        if proc.returncode == 2:
            outcome.blocked = True
            outcome.reason = (proc.stderr or stdout or "blocked by hook").strip()
