"""DeepSeek provider — OpenAI-compatible chat completions dialect.

Also serves as the template for any OpenAI-compatible API (OpenAI, Ollama,
Together, Groq, ...): only the base URL, auth header, and model registry differ.
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


class DeepSeekProvider(Provider):
    name = "deepseek"
    base_url = "https://api.deepseek.com"

    def capabilities(self, model: str) -> ModelCapabilities:
        return registry_lookup(self.name, model)

    # ---- request building --------------------------------------------------------
    def _headers(self, api_key: str) -> dict:
        return {"Authorization": f"Bearer {api_key}"}

    def _tools_wire(self, tools: list[ToolSchema] | None) -> list[dict] | None:
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in tools
        ]

    def _messages_wire(self, messages: list[Message], system: str | None) -> list[dict]:
        out: list[dict] = []
        if system:
            out.append({"role": "system", "content": system})
        for m in messages:
            if m.role == "system":
                out.append({"role": "system", "content": m.text()})
            elif m.role == "user":
                out.append({"role": "user", "content": _user_content(m)})
            elif m.role == "assistant":
                out.append(_assistant_wire(m))
            elif m.role == "tool":
                # one OpenAI `tool` message per result block. OpenAI tool messages
                # can't hold images, so emit a follow-up user message with the image.
                image_parts = []
                for b in m.content:
                    if isinstance(b, ToolResultBlock):
                        out.append({
                            "role": "tool",
                            "tool_call_id": b.tool_use_id,
                            "content": b.content or "[image output below]",
                        })
                        for img in b.images:
                            image_parts.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{img['media_type']};base64,{img['data']}"}})
                if image_parts:
                    out.append({"role": "user",
                                "content": [{"type": "text",
                                             "text": "(image output of the previous tool call)"}]
                                           + image_parts})
        return out

    # ---- main entry --------------------------------------------------------------
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
            raise ProviderError("deepseek: missing api_key (BYOK)")

        body: dict = {
            "model": model,
            "messages": self._messages_wire(messages, system),
            "stream": stream,
        }
        wire_tools = self._tools_wire(tools)
        if wire_tools:
            body["tools"] = wire_tools
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if stream:
            body["stream_options"] = {"include_usage": True}
        if extra:
            body.update(extra)

        url = f"{self.base_url}/chat/completions"
        if stream:
            yield from stream_with_retry(lambda: self._stream(url, api_key, body))
        else:
            yield from stream_with_retry(lambda: self._once(url, api_key, body))

    # ---- non-streaming -----------------------------------------------------------
    def _once(self, url: str, api_key: str, body: dict) -> Iterator[StreamEvent]:
        try:
            data = post_json(url, self._headers(api_key), body)
        except HTTPError as e:
            yield StreamEvent.failure(f"deepseek HTTP {e.status}: {e.body[:300]}")
            return
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message", {})
        if msg.get("content"):
            yield StreamEvent.text_delta(msg["content"])
        for tc in msg.get("tool_calls", []) or []:
            fn = tc.get("function", {})
            yield StreamEvent.tool(tc.get("id", ""), fn.get("name", ""), _safe_json(fn.get("arguments", "{}")))
        usage = data.get("usage") or {}
        if usage:
            yield StreamEvent.usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        yield StreamEvent.finished(choice.get("finish_reason", "stop"))

    # ---- streaming ---------------------------------------------------------------
    def _stream(self, url: str, api_key: str, body: dict) -> Iterator[StreamEvent]:
        # accumulate tool calls by index across deltas
        tool_acc: dict[int, dict] = {}
        finish_reason = "stop"
        try:
            for sse in post_sse(url, self._headers(api_key), body):
                if sse.data.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(sse.data)
                except json.JSONDecodeError:
                    continue

                usage = chunk.get("usage")
                if usage:
                    yield StreamEvent.usage(
                        usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
                    )

                for choice in chunk.get("choices", []) or []:
                    delta = choice.get("delta", {}) or {}
                    if delta.get("content"):
                        yield StreamEvent.text_delta(delta["content"])
                    # reasoning_content: DeepSeek-R1 style thinking stream
                    if delta.get("reasoning_content"):
                        yield StreamEvent.thinking_delta(delta["reasoning_content"])
                    for tc in delta.get("tool_calls", []) or []:
                        idx = tc.get("index", 0)
                        acc = tool_acc.setdefault(idx, {"id": "", "name": "", "args": ""})
                        if tc.get("id"):
                            acc["id"] = tc["id"]
                        fn = tc.get("function", {}) or {}
                        if fn.get("name"):
                            acc["name"] = fn["name"]
                        if fn.get("arguments"):
                            acc["args"] += fn["arguments"]
                    if choice.get("finish_reason"):
                        finish_reason = choice["finish_reason"]
        except HTTPError as e:
            yield StreamEvent.failure(f"deepseek HTTP {e.status}: {e.body[:300]}")
            return

        # flush accumulated tool calls
        for idx in sorted(tool_acc):
            acc = tool_acc[idx]
            if acc["name"]:
                yield StreamEvent.tool(acc["id"], acc["name"], _safe_json(acc["args"] or "{}"))
        yield StreamEvent.finished(finish_reason)


# ---- wire helpers ----------------------------------------------------------------

def _user_content(m: Message):
    """Return a plain string, or an OpenAI content array if images are present."""
    has_image = any(isinstance(b, ImageBlock) for b in m.content)
    if not has_image:
        return m.text()
    parts = []
    for b in m.content:
        if isinstance(b, TextBlock):
            parts.append({"type": "text", "text": b.text})
        elif isinstance(b, ImageBlock):
            parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:{b.media_type};base64,{b.data}"},
            })
    return parts


def _assistant_wire(m: Message) -> dict:
    text_parts = [b.text for b in m.content if isinstance(b, TextBlock)]
    tool_calls = []
    for b in m.content:
        if isinstance(b, ToolUseBlock):
            tool_calls.append({
                "id": b.id,
                "type": "function",
                "function": {"name": b.name, "arguments": json.dumps(b.input)},
            })
    msg: dict = {"role": "assistant", "content": "".join(text_parts) or None}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg


def _safe_json(s: str) -> dict:
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else {"value": v}
    except (json.JSONDecodeError, TypeError):
        return {}
