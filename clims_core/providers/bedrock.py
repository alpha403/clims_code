"""Anthropic-on-AWS-Bedrock provider (SigV4-signed, non-streaming /invoke).

Credentials come from the standard AWS env vars (BYOK):
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN (optional),
    AWS_REGION (or CLIMS_BEDROCK_REGION).
The body is the Anthropic Messages format with `anthropic_version` and no `model`
(model id is in the URL). Response JSON is parsed identically to the direct API.
"""
from __future__ import annotations

import datetime
import json
import os
from typing import Iterator

from clims_core.http import post_raw, HTTPError
from clims_core.providers.anthropic import AnthropicProvider
from clims_core.providers._sigv4 import sign
from clims_core.providers.base import StreamEvent, ProviderError


class BedrockAnthropicProvider(AnthropicProvider):
    name = "bedrock"

    def _region(self) -> str:
        return os.environ.get("CLIMS_BEDROCK_REGION") or os.environ.get("AWS_REGION", "us-east-1")

    def endpoint(self, model: str) -> str:
        region = self._region()
        return f"https://bedrock-runtime.{region}.amazonaws.com/model/{model}/invoke"

    def chat(self, *, model, messages, tools=None, system=None, api_key="",
             stream=True, temperature=None, max_tokens=None, extra=None) -> Iterator[StreamEvent]:
        access = os.environ.get("AWS_ACCESS_KEY_ID")
        secret = os.environ.get("AWS_SECRET_ACCESS_KEY")
        if not access or not secret:
            raise ProviderError("bedrock: AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY not set")
        session_token = os.environ.get("AWS_SESSION_TOKEN")
        region = self._region()
        caps = self.capabilities(model)

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens or caps.max_output,
            "messages": self._messages_wire(messages),
        }
        sys_text = "\n".join(s for s in (system or "", *[m.text() for m in messages if m.role == "system"]) if s)
        if sys_text:
            body["system"] = sys_text
        tw = self._tools_wire(tools)
        if tw:
            body["tools"] = tw
        if temperature is not None:
            body["temperature"] = temperature
        if extra:
            body.update(extra)

        payload = json.dumps(body).encode("utf-8")
        url = self.endpoint(model)
        amz_date = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        signed = sign("POST", url, region, "bedrock", access, secret,
                      {"content-type": "application/json"}, payload, amz_date,
                      session_token=session_token)
        signed["content-type"] = "application/json"

        try:
            data = post_raw(url, signed, payload)
        except HTTPError as e:
            yield StreamEvent.failure(f"bedrock HTTP {e.status}: {e.body[:300]}")
            return
        # response is the standard Anthropic message JSON
        for block in data.get("content", []) or []:
            t = block.get("type")
            if t == "text":
                yield StreamEvent.text_delta(block.get("text", ""))
            elif t == "thinking":
                yield StreamEvent.thinking_delta(block.get("thinking", ""))
            elif t == "tool_use":
                yield StreamEvent.tool(block.get("id", ""), block.get("name", ""), block.get("input", {}) or {})
        usage = data.get("usage") or {}
        if usage:
            yield StreamEvent.usage(usage.get("input_tokens", 0), usage.get("output_tokens", 0))
        yield StreamEvent.finished(data.get("stop_reason", "end_turn"))
