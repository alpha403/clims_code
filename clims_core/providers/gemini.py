"""Google Gemini provider — a third, distinct dialect.

Gemini differs from both OpenAI and Anthropic:
  - roles are "user" and "model" (not "assistant")
  - tool calls are `functionCall` parts; results are `functionResponse` parts
    matched by tool NAME (not id) — so we recover names from prior functionCalls
  - system goes in `systemInstruction`
  - key travels in the `x-goog-api-key` header (kept out of the URL)

Implementing a third dialect cleanly is the real test that the normalization
layer holds. (Wire-format unit-tested; needs a live key to confirm end-to-end,
same as the Anthropic adapter.)
"""
from __future__ import annotations

import json
from typing import Iterator

from clims_core.agent.message import (
    Message, TextBlock, ThinkingBlock, ImageBlock, ToolUseBlock, ToolResultBlock,
)
from clims_core.http import post_sse, post_json, HTTPError
from clims_core.providers.base import (
    Provider, ProviderError, StreamEvent, ModelCapabilities, ToolSchema, stream_with_retry,
)
from clims_core.providers.registry import lookup as registry_lookup


class GeminiProvider(Provider):
    name = "gemini"
    base_url = "https://generativelanguage.googleapis.com/v1beta"

    def capabilities(self, model: str) -> ModelCapabilities:
        return registry_lookup(self.name, model)

    def _headers(self, api_key: str) -> dict:
        return {"x-goog-api-key": api_key}

    def _tools_wire(self, tools: list[ToolSchema] | None):
        if not tools:
            return None
        return [{"functionDeclarations": [
            {"name": t.name, "description": t.description, "parameters": t.input_schema}
            for t in tools
        ]}]

    def _name_for_id(self, messages: list[Message]) -> dict:
        """Map tool_use_id -> tool name from assistant functionCalls (Gemini matches
        responses to calls by name)."""
        m = {}
        for msg in messages:
            for b in msg.content:
                if isinstance(b, ToolUseBlock):
                    m[b.id] = b.name
        return m

    def _contents_wire(self, messages: list[Message]) -> list[dict]:
        id2name = self._name_for_id(messages)
        out = []
        for msg in messages:
            if msg.role == "system":
                continue
            if msg.role == "tool":
                parts = []
                image_parts = []
                for b in msg.content:
                    if isinstance(b, ToolResultBlock):
                        parts.append({"functionResponse": {
                            "name": id2name.get(b.tool_use_id, b.tool_use_id),
                            "response": {"result": b.content},
                        }})
                        for img in b.images:
                            image_parts.append({"inlineData": {
                                "mimeType": img["media_type"], "data": img["data"]}})
                out.append({"role": "user", "parts": parts})
                if image_parts:  # Gemini takes images as inlineData parts in a user turn
                    out.append({"role": "user",
                                "parts": [{"text": "(image output of the tool)"}] + image_parts})
                continue
            role = "model" if msg.role == "assistant" else "user"
            out.append({"role": role, "parts": _parts_wire(msg)})
        return out

    def chat(self, *, model, messages, tools=None, system=None, api_key,
             stream=True, temperature=None, max_tokens=None, extra=None) -> Iterator[StreamEvent]:
        if not api_key:
            raise ProviderError("gemini: missing api_key (BYOK)")

        body: dict = {"contents": self._contents_wire(messages)}
        sys_text = system or ""
        extra_sys = "\n".join(m.text() for m in messages if m.role == "system")
        sys_text = "\n".join(s for s in (sys_text, extra_sys) if s)
        if sys_text:
            body["systemInstruction"] = {"parts": [{"text": sys_text}]}
        wire_tools = self._tools_wire(tools)
        if wire_tools:
            body["tools"] = wire_tools
        gen_cfg = {}
        if temperature is not None:
            gen_cfg["temperature"] = temperature
        if max_tokens is not None:
            gen_cfg["maxOutputTokens"] = max_tokens
        if gen_cfg:
            body["generationConfig"] = gen_cfg
        if extra:
            body.update(extra)

        if stream:
            url = f"{self.base_url}/models/{model}:streamGenerateContent?alt=sse"
            yield from stream_with_retry(lambda: self._stream(url, api_key, body))
        else:
            url = f"{self.base_url}/models/{model}:generateContent"
            yield from stream_with_retry(lambda: self._once(url, api_key, body))

    def _emit_candidates(self, data: dict, counter: list) -> Iterator[StreamEvent]:
        for cand in data.get("candidates", []) or []:
            content = cand.get("content", {}) or {}
            for part in content.get("parts", []) or []:
                if "text" in part and part["text"]:
                    yield StreamEvent.text_delta(part["text"])
                fc = part.get("functionCall")
                if fc:
                    counter[0] += 1
                    yield StreamEvent.tool(f"gemini_{counter[0]}", fc.get("name", ""),
                                           fc.get("args", {}) or {})

    def _once(self, url, api_key, body) -> Iterator[StreamEvent]:
        try:
            data = post_json(url, self._headers(api_key), body)
        except HTTPError as e:
            yield StreamEvent.failure(f"gemini HTTP {e.status}: {e.body[:300]}")
            return
        counter = [0]
        yield from self._emit_candidates(data, counter)
        usage = data.get("usageMetadata", {}) or {}
        if usage:
            yield StreamEvent.usage(usage.get("promptTokenCount", 0),
                                    usage.get("candidatesTokenCount", 0))
        fr = (data.get("candidates", [{}]) or [{}])[0].get("finishReason", "STOP")
        yield StreamEvent.finished(fr or "STOP")

    def _stream(self, url, api_key, body) -> Iterator[StreamEvent]:
        counter = [0]
        stop_reason = "STOP"
        in_tok = out_tok = 0
        try:
            for sse in post_sse(url, self._headers(api_key), body):
                if not sse.data or sse.data.strip() == "[DONE]":
                    continue
                try:
                    chunk = json.loads(sse.data)
                except json.JSONDecodeError:
                    continue
                yield from self._emit_candidates(chunk, counter)
                usage = chunk.get("usageMetadata", {}) or {}
                if usage:
                    in_tok = usage.get("promptTokenCount", in_tok)
                    out_tok = usage.get("candidatesTokenCount", out_tok)
                for cand in chunk.get("candidates", []) or []:
                    if cand.get("finishReason"):
                        stop_reason = cand["finishReason"]
        except HTTPError as e:
            yield StreamEvent.failure(f"gemini HTTP {e.status}: {e.body[:300]}")
            return
        if in_tok or out_tok:
            yield StreamEvent.usage(in_tok, out_tok)
        yield StreamEvent.finished(stop_reason)


def _parts_wire(m: Message) -> list[dict]:
    parts = []
    for b in m.content:
        if isinstance(b, TextBlock):
            parts.append({"text": b.text})
        elif isinstance(b, ThinkingBlock):
            parts.append({"text": b.text})
        elif isinstance(b, ImageBlock):
            parts.append({"inlineData": {"mimeType": b.media_type, "data": b.data}})
        elif isinstance(b, ToolUseBlock):
            parts.append({"functionCall": {"name": b.name, "args": b.input}})
    return parts or [{"text": ""}]
