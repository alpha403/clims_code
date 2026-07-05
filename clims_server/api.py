"""HTTP API for the clims_code engine.

Endpoints (see docs/04-API.md):
  GET  /healthz                          -> {"status":"ok"}
  GET  /v1/models                        -> [{provider,model,...}]
  POST /v1/sessions                      -> {"session_id": ...}
  GET  /v1/sessions/{id}                 -> {"session_id", "messages":[...]}
  POST /v1/sessions/{id}/messages        -> SSE stream of agent events

BYOK: request body carries provider/model/api_key. The key is used in-memory and
NEVER logged or persisted. Product-level auth (who may call this server) is via
the X-Clims-Token header, checked only if CLIMS_SERVER_TOKEN is set.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from clims_core.agent.loop import Agent
from clims_core.agent.message import Message
from clims_core.agent.runtime import ToolRuntime
from clims_core.permissions.policy import PermissionMode, PermissionPolicy
from clims_core.providers import get_provider
from clims_core.providers.registry import list_models
from clims_core.tools import default_tools, tool_map
from clims_core.tools.base import ToolContext
from pathlib import Path


from clims_core.session.store import MemorySessionStore, SQLiteSessionStore


def _make_store():
    """Durable sqlite store if CLIMS_DB is set, else in-memory. Holds only
    conversation messages — never api keys."""
    db = os.environ.get("CLIMS_DB")
    return SQLiteSessionStore(db) if db else MemorySessionStore()


STORE = _make_store()


def _auth_ok(handler: "Handler") -> bool:
    required = os.environ.get("CLIMS_SERVER_TOKEN")
    if not required:
        return True  # auth disabled
    return handler.headers.get("X-Clims-Token") == required


class Handler(BaseHTTPRequestHandler):
    # HTTP/1.0 semantics: each response closes the connection. This keeps SSE
    # streaming correct without chunked encoding (client reads to EOF) and is
    # fine behind a reverse proxy, which handles client-side keep-alive/TLS.
    protocol_version = "HTTP/1.0"
    server_version = "clims_code/0.1"

    # ---- helpers ----
    def _json(self, code: int, obj: dict):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def log_message(self, *args):  # silence default logging (avoid leaking anything)
        pass

    # ---- routing ----
    def do_GET(self):
        if self.path == "/healthz":
            return self._json(200, {"status": "ok", "version": "0.1.0"})
        if not _auth_ok(self):
            return self._json(401, {"error": "unauthorized"})
        if self.path == "/v1/models":
            return self._json(200, {"models": list_models()})
        if self.path.startswith("/v1/sessions/"):
            sid = self.path.split("/v1/sessions/", 1)[1].split("/")[0]
            msgs = STORE.get(sid)
            if msgs is None:
                return self._json(404, {"error": "session not found"})
            return self._json(200, {"session_id": sid,
                                    "messages": [m.to_dict() for m in msgs]})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        # Always consume the request body first so no unread bytes remain on the
        # socket (unread data causes a connection reset on close, esp. on Windows).
        body = self._read_body()
        # OpenAI-compatible shim: bearer IS the BYOK key (no separate product auth)
        if self.path == "/v1/chat/completions":
            return self._handle_openai_chat(body)
        if not _auth_ok(self):
            return self._json(401, {"error": "unauthorized"})
        if self.path == "/v1/sessions":
            return self._json(200, {"session_id": STORE.create()})
        if self.path.startswith("/v1/sessions/") and self.path.endswith("/messages"):
            sid = self.path.split("/v1/sessions/", 1)[1].split("/")[0]
            return self._handle_message(sid, body)
        return self._json(404, {"error": "not found"})

    # ---- the streaming endpoint ----
    def _handle_message(self, sid: str, body: dict):
        if not STORE.exists(sid):
            return self._json(404, {"error": "session not found"})
        api_key = body.get("api_key", "")
        provider_name = body.get("provider", "deepseek")
        model = body.get("model", "deepseek-chat")
        user_msg = body.get("message", "")
        mode = body.get("permission_mode", "default")
        if not api_key:
            return self._json(400, {"error": "missing api_key (BYOK)"})
        if not user_msg:
            return self._json(400, {"error": "missing message"})

        try:
            provider = get_provider(provider_name)
        except ValueError as e:
            return self._json(400, {"error": str(e)})

        # build agent
        tools = default_tools()
        policy = PermissionPolicy(mode=_safe_mode(mode),
                                  allow=body.get("allow", []),
                                  deny=body.get("deny", []),
                                  ask=body.get("ask", []))
        ctx = ToolContext(cwd=Path(os.environ.get("CLIMS_WORKDIR", ".")))
        # over the API, ASK auto-denies (no interactive channel yet); emit the
        # request event so a future bidirectional client can handle it.
        runtime = ToolRuntime(tool_map(tools), policy, ctx, approve=lambda *a: False)
        agent = Agent(provider=provider, model=model, api_key=api_key, runtime=runtime)

        history = STORE.get(sid) or []
        history.append(Message.user(user_msg))

        # start SSE
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        def emit(ev):
            payload = _event_payload(ev)
            try:
                chunk = f"event: {ev.type}\ndata: {json.dumps(payload)}\n\n".encode("utf-8")
                self.wfile.write(chunk)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                raise

        try:
            result = agent.send(history, emit)
            STORE.set(sid, result.messages)
        except Exception as e:
            try:
                err = f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
                self.wfile.write(err.encode("utf-8"))
                self.wfile.flush()
            except Exception:
                pass


    def _handle_openai_chat(self, body: dict):
        """OpenAI-compatible /v1/chat/completions shim — a plain completion proxy
        (no agentic tools), so existing OpenAI SDK clients work with a base-url swap.
        BYOK key arrives as `Authorization: Bearer <key>`."""
        auth = self.headers.get("Authorization", "")
        api_key = auth[len("Bearer "):].strip() if auth.startswith("Bearer ") else ""
        if not api_key:
            return self._json(401, {"error": {"message": "missing bearer api key"}})
        model = body.get("model", "deepseek-chat")
        provider_name = self.headers.get("x-clims-provider") or body.get("provider", "deepseek")
        try:
            provider = get_provider(provider_name)
        except ValueError as e:
            return self._json(400, {"error": {"message": str(e)}})

        # convert OpenAI messages -> normalized; hoist system text
        system_parts, msgs = [], []
        for m in body.get("messages", []):
            role = m.get("role")
            content = m.get("content")
            text = content if isinstance(content, str) else _flatten_openai_content(content)
            if role == "system":
                system_parts.append(text)
            elif role == "assistant":
                msgs.append(Message.assistant(text))
            else:
                msgs.append(Message.user(text))
        system = "\n".join(system_parts) or None
        stream = bool(body.get("stream", False))
        temperature = body.get("temperature")
        max_tokens = body.get("max_tokens")
        cid = "chatcmpl-" + uuid.uuid4().hex[:24]

        def call(stream_flag):
            return provider.chat(model=model, messages=msgs, tools=None, system=system,
                                 api_key=api_key, stream=stream_flag,
                                 temperature=temperature, max_tokens=max_tokens)

        if not stream:
            text, in_tok, out_tok, stop = "", 0, 0, "stop"
            try:
                for ev in call(False):
                    if ev.type == "text_delta":
                        text += ev.text
                    elif ev.type == "usage":
                        in_tok, out_tok = ev.input_tokens, ev.output_tokens
                    elif ev.type == "done":
                        stop = ev.stop_reason or stop
                    elif ev.type == "error":
                        return self._json(502, {"error": {"message": ev.message}})
            except Exception as e:
                return self._json(502, {"error": {"message": str(e)}})
            return self._json(200, {
                "id": cid, "object": "chat.completion", "model": model,
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": text}}],
                "usage": {"prompt_tokens": in_tok, "completion_tokens": out_tok,
                          "total_tokens": in_tok + out_tok},
            })

        # streaming: OpenAI chat.completion.chunk SSE
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        def emit_chunk(delta: dict, finish=None):
            chunk = {"id": cid, "object": "chat.completion.chunk", "model": model,
                     "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
            self.wfile.flush()
        try:
            emit_chunk({"role": "assistant"})
            for ev in call(True):
                if ev.type == "text_delta":
                    emit_chunk({"content": ev.text})
                elif ev.type == "error":
                    emit_chunk({}, finish="stop")
                    break
            emit_chunk({}, finish="stop")
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except Exception:
            pass


def _flatten_openai_content(content) -> str:
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return str(content or "")


def _safe_mode(mode: str) -> PermissionMode:
    try:
        return PermissionMode(mode)
    except ValueError:
        return PermissionMode.DEFAULT


def _event_payload(ev) -> dict:
    if ev.type in ("text_delta", "thinking_delta"):
        return {"text": ev.text}
    if ev.type == "tool_use":
        return {"id": ev.tool_id, "name": ev.tool_name, "input": ev.tool_input}
    if ev.type == "permission_request":
        return {"tool_use_id": ev.tool_id, "tool": ev.tool_name, "input": ev.tool_input}
    if ev.type == "tool_result":
        return {"tool_use_id": ev.tool_id, "tool": ev.tool_name,
                "is_error": ev.is_error, "content": ev.message}
    if ev.type == "usage":
        return {"input_tokens": ev.input_tokens, "output_tokens": ev.output_tokens}
    if ev.type == "done":
        return {"stop_reason": ev.stop_reason}
    if ev.type == "error":
        return {"message": ev.message}
    return {}


def create_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


def serve(host: str = "127.0.0.1", port: int = 8765):
    srv = create_server(host, port)
    print(f"clims_code server on http://{host}:{port}  (auth: "
          f"{'on' if os.environ.get('CLIMS_SERVER_TOKEN') else 'off'})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    serve(host=os.environ.get("CLIMS_HOST", "127.0.0.1"),
          port=int(os.environ.get("CLIMS_PORT", "8765")))
