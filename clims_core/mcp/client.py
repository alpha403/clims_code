"""stdio MCP client — JSON-RPC 2.0 over newline-delimited stdio.

Implements the subset needed to use a server's tools:
  initialize -> notifications/initialized -> tools/list -> tools/call

A background reader thread consumes the server's stdout and routes responses to
the waiting request by id. Stderr is drained separately (server logs).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
from dataclasses import dataclass

PROTOCOL_VERSION = "2024-11-05"


class MCPError(Exception):
    pass


@dataclass
class MCPToolSpec:
    name: str
    description: str
    input_schema: dict


class StdioMCPClient:
    def __init__(self, command: str, args: list[str] | None = None,
                 env: dict | None = None, name: str = "mcp"):
        self.command = command
        self.args = args or []
        self.env = env
        self.name = name
        self.proc: subprocess.Popen | None = None
        self._id = 0
        self._id_lock = threading.Lock()
        self._pending: dict[int, dict] = {}
        self._events: dict[int, threading.Event] = {}
        self._reader: threading.Thread | None = None
        self._closed = False

    # ---- lifecycle ----
    def start(self, init_timeout: float = 15.0) -> "StdioMCPClient":
        import os
        full_env = dict(os.environ)
        if self.env:
            full_env.update(self.env)
        # Resolve the command to its full path so Windows finds .cmd/.exe shims
        # (e.g. npx -> npx.cmd); shutil.which respects PATH + PATHEXT.
        resolved = shutil.which(self.command) or self.command
        # On Windows, .cmd/.bat shims must be launched through the shell.
        use_shell = os.name == "nt" and str(resolved).lower().endswith((".cmd", ".bat"))
        popen_arg = (subprocess.list2cmdline([resolved, *self.args])
                     if use_shell else [resolved, *self.args])
        self.proc = subprocess.Popen(
            popen_arg,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, env=full_env, shell=use_shell,
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._drain = threading.Thread(target=self._drain_stderr, daemon=True)
        self._drain.start()
        self._initialize(init_timeout)
        return self

    def _initialize(self, timeout: float):
        self.request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "clims_code", "version": "0.1.0"},
        }, timeout=timeout)
        self.notify("notifications/initialized", {})

    # ---- io ----
    def _next_id(self) -> int:
        with self._id_lock:
            self._id += 1
            return self._id

    def _send(self, obj: dict):
        if not self.proc or self.proc.stdin is None:
            raise MCPError(f"{self.name}: process not started")
        line = json.dumps(obj) + "\n"
        try:
            self.proc.stdin.write(line)
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise MCPError(f"{self.name}: write failed: {e}") from None

    def _read_loop(self):
        assert self.proc and self.proc.stdout
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            mid = msg.get("id")
            if mid is not None and mid in self._events:
                self._pending[mid] = msg
                self._events[mid].set()
            # messages without a known id are notifications/logs -> ignore

    def _drain_stderr(self):
        assert self.proc and self.proc.stderr
        for _ in self.proc.stderr:
            pass  # discard; could route to a logger

    def notify(self, method: str, params: dict):
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def request(self, method: str, params: dict, timeout: float = 30.0) -> dict:
        mid = self._next_id()
        ev = threading.Event()
        self._events[mid] = ev
        self._send({"jsonrpc": "2.0", "id": mid, "method": method, "params": params})
        if not ev.wait(timeout):
            self._events.pop(mid, None)
            raise MCPError(f"{self.name}: timeout waiting for '{method}'")
        msg = self._pending.pop(mid, {})
        self._events.pop(mid, None)
        if "error" in msg:
            err = msg["error"]
            raise MCPError(f"{self.name}: {method} error {err.get('code')}: {err.get('message')}")
        return msg.get("result", {})

    # ---- high-level ----
    def list_tools(self) -> list[MCPToolSpec]:
        result = self.request("tools/list", {})
        specs = []
        for t in result.get("tools", []):
            specs.append(MCPToolSpec(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema") or t.get("input_schema") or {"type": "object"},
            ))
        return specs

    def list_resources(self) -> list[dict]:
        return self.request("resources/list", {}).get("resources", [])

    def read_resource(self, uri: str) -> list[dict]:
        return self.request("resources/read", {"uri": uri}).get("contents", [])

    def list_prompts(self) -> list[dict]:
        return self.request("prompts/list", {}).get("prompts", [])

    def get_prompt(self, name: str, arguments: dict | None = None) -> dict:
        return self.request("prompts/get", {"name": name, "arguments": arguments or {}})

    def call_tool(self, name: str, arguments: dict, timeout: float = 120.0) -> tuple[str, bool]:
        """Return (text_content, is_error)."""
        result = self.request("tools/call", {"name": name, "arguments": arguments},
                              timeout=timeout)
        is_error = bool(result.get("isError", False))
        parts = []
        for block in result.get("content", []) or []:
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
            else:
                parts.append(json.dumps(block))
        return ("\n".join(parts), is_error)

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self.proc:
            try:
                if self.proc.stdin:
                    self.proc.stdin.close()
            except OSError:
                pass
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
