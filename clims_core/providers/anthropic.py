"""Anthropic provider — block-based Messages API dialect.

Deliberately a *different* wire shape from DeepSeek (content blocks, top-level
system, tool_result inside user messages) to prove the normalization layer holds.
"""
from __future__ import annotations

import json
from typing import Iterator

from clims_core.agent.message import (
    Message,
    TextBlock,
    ThinkingBlock,
    ImageBlock,
    ToolUseBlock,
    ToolResultBlock,
)
from clims_core.http import post_sse, post_json, HTTPError
from clims_core.providers.base import (
    Provider,
    ProviderError,
    StreamEvent,
    ModelCapabilities,
    ToolSchema,
    stream_with_retry,
)
from clims_core.providers.registry import lookup as registry_lookup

ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(Provider):
    name = "anthropic"
    base_url = "https://api.anthropic.com"

    def capabilities(self, model: str) -> ModelCapabilities:
        return registry_lookup(self.name, model)

    def _headers(self, api_key: str) -> dict:
        return {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }

    def _tools_wire(self, tools: list[ToolSchema] | None) -> list[dict] | None:
        if not tools:
            return None
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]

    def _messages_wire(self, messages: list[Message]) -> list[dict]:
        out: list[dict] = []
        for m in messages:
            if m.role == "system":
                continue  # system is hoisted to top-level
            if m.role == "tool":
                # Anthropic carries tool results inside a *user* message; images go
                # natively in the tool_result content as image blocks.
                blocks = []
                for b in m.content:
                    if not isinstance(b, ToolResultBlock):
                        continue
                    block = {"type": "tool_result", "tool_use_id": b.tool_use_id}
                    if b.images:
                        inner = []
                        if b.content:
                            inner.append({"type": "text", "text": b.content})
                        for img in b.images:
                            inner.append({"type": "image", "source": {
                                "type": "base64", "media_type": img["media_type"],
                                "data": img["data"]}})
                        block["content"] = inner
                    else:
                        block["content"] = b.content
                    if b.is_error:
                        block["is_error"] = True
                    blocks.append(block)
                out.append({"role": "user", "content": blocks})
                continue
            role = "assistant" if m.role == "assistant" else "user"
            out.append({"role": role, "content": _blocks_wire(m)})
        return out

    def chat(
        self,
        *,
        model: str,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        system: str | None = None,
        api_key: str,
        stream: bool = True,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra: dict | None = None,
    ) -> Iterator[StreamEvent]:
        if not api_key:
            raise ProviderError("anthropic: missing api_key (BYOK)")

        caps = self.capabilities(model)
        body: dict = {
            "model": model,
            "max_tokens": max_tokens or caps.max_output,
            "messages": self._messages_wire(messages),
            "stream": stream,
        }
        # gather system text from explicit param + any system messages
        sys_text = system or ""
        extra_sys = "\n".join(m.text() for m in messages if m.role == "system")
        sys_text = "\n".join(s for s in (sys_text, extra_sys) if s)
        if sys_text:
            # prompt caching: cache the (large, stable) system prompt when supported
            if caps.supports_prompt_cache:
                body["system"] = [{"type": "text", "text": sys_text,
                                   "cache_control": {"type": "ephemeral"}}]
            else:
                body["system"] = sys_text
        wire_tools = self._tools_wire(tools)
        if wire_tools:
            body["tools"] = wire_tools
        if temperature is not None:
            body["temperature"] = temperature
        if extra:
            body.update(extra)

        url = f"{self.base_url}/v1/messages"
        if stream:
            yield from stream_with_retry(lambda: self._stream(url, api_key, body))
        else:
            yield from stream_with_retry(lambda: self._once(url, api_key, body))

    def _once(self, url: str, api_key: str, body: dict) -> Iterator[StreamEvent]:
        try:
            data = post_json(url, self._headers(api_key), body)
        except HTTPError as e:
            yield StreamEvent.failure(f"anthropic HTTP {e.status}: {e.body[:300]}")
            return
        for block in data.get("content", []) or []:
            btype = block.get("type")
            if btype == "text":
                yield StreamEvent.text_delta(block.get("text", ""))
            elif btype == "thinking":
                yield StreamEvent.thinking_delta(block.get("thinking", ""))
            elif btype == "tool_use":
                yield StreamEvent.tool(block.get("id", ""), block.get("name", ""), block.get("input", {}) or {})
        usage = data.get("usage") or {}
        if usage:
            yield StreamEvent.usage(usage.get("input_tokens", 0), usage.get("output_tokens", 0))
        yield StreamEvent.finished(data.get("stop_reason", "end_turn"))

    def _stream(self, url: str, api_key: str, body: dict) -> Iterator[StreamEvent]:
        # per-index accumulation for tool_use input_json_delta
        blocks: dict[int, dict] = {}
        stop_reason = "end_turn"
        in_tokens = 0
        out_tokens = 0
        try:
            for sse in post_sse(url, self._headers(api_key), body):
                if not sse.data:
                    continue
                try:
                    ev = json.loads(sse.data)
                except json.JSONDecodeError:
                    continue
                etype = ev.get("type") or sse.event

                if etype == "message_start":
                    usage = (ev.get("message", {}) or {}).get("usage", {}) or {}
                    in_tokens = usage.get("input_tokens", 0)
                elif etype == "content_block_start":
                    idx = ev.get("index", 0)
                    cb = ev.get("content_block", {}) or {}
                    blocks[idx] = {"type": cb.get("type"), "id": cb.get("id", ""),
                                   "name": cb.get("name", ""), "json": ""}
                elif etype == "content_block_delta":
                    idx = ev.get("index", 0)
                    delta = ev.get("delta", {}) or {}
                    dtype = delta.get("type")
                    if dtype == "text_delta":
                        yield StreamEvent.text_delta(delta.get("text", ""))
                    elif dtype == "thinking_delta":
                        yield StreamEvent.thinking_delta(delta.get("thinking", ""))
                    elif dtype == "input_json_delta":
                        blocks.setdefault(idx, {"type": "tool_use", "id": "", "name": "", "json": ""})
                        blocks[idx]["json"] += delta.get("partial_json", "")
                elif etype == "content_block_stop":
                    idx = ev.get("index", 0)
                    b = blocks.get(idx)
                    if b and b.get("type") == "tool_use":
                        try:
                            inp = json.loads(b["json"]) if b["json"] else {}
                        except json.JSONDecodeError:
                            inp = {}
                        yield StreamEvent.tool(b["id"], b["name"], inp)
                elif etype == "message_delta":
                    delta = ev.get("delta", {}) or {}
                    if delta.get("stop_reason"):
                        stop_reason = delta["stop_reason"]
                    usage = ev.get("usage", {}) or {}
                    if usage.get("output_tokens"):
                        out_tokens = usage["output_tokens"]
                elif etype == "error":
                    err = ev.get("error", {}) or {}
                    yield StreamEvent.failure(f"anthropic: {err.get('message', 'stream error')}")
                    return
                elif etype == "message_stop":
                    break
        except HTTPError as e:
            yield StreamEvent.failure(f"anthropic HTTP {e.status}: {e.body[:300]}")
            return

        if in_tokens or out_tokens:
            yield StreamEvent.usage(in_tokens, out_tokens)
        yield StreamEvent.finished(stop_reason)


# ---- wire helpers ----------------------------------------------------------------

def _blocks_wire(m: Message) -> list[dict]:
    out: list[dict] = []
    for b in m.content:
        if isinstance(b, TextBlock):
            out.append({"type": "text", "text": b.text})
        elif isinstance(b, ThinkingBlock):
            blk = {"type": "thinking", "thinking": b.text}
            if b.signature:
                blk["signature"] = b.signature
            out.append(blk)
        elif isinstance(b, ImageBlock):
            out.append({
                "type": "image",
                "source": {"type": "base64", "media_type": b.media_type, "data": b.data},
            })
        elif isinstance(b, ToolUseBlock):
            out.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
    # Anthropic requires non-empty content; fall back to a single empty text block
    return out or [{"type": "text", "text": ""}]
