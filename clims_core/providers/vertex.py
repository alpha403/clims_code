"""Anthropic-on-Google-Vertex provider (bearer-token auth, non-streaming).

BYOK: the api_key is a GCP OAuth access token. Project/region come from
CLIMS_VERTEX_PROJECT / CLIMS_VERTEX_REGION (or env GOOGLE_CLOUD_PROJECT).
Body is the Anthropic Messages format with `anthropic_version` and no `model`.
"""
from __future__ import annotations

import os
from typing import Iterator

from clims_core.http import post_json, HTTPError
from clims_core.providers.anthropic import AnthropicProvider
from clims_core.providers.base import StreamEvent, ProviderError


class VertexAnthropicProvider(AnthropicProvider):
    name = "vertex"

    def _project(self) -> str:
        return os.environ.get("CLIMS_VERTEX_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT", "")

    def _region(self) -> str:
        return os.environ.get("CLIMS_VERTEX_REGION", "us-east5")

    def endpoint(self, model: str) -> str:
        region, project = self._region(), self._project()
        return (f"https://{region}-aiplatform.googleapis.com/v1/projects/{project}/"
                f"locations/{region}/publishers/anthropic/models/{model}:rawPredict")

    def chat(self, *, model, messages, tools=None, system=None, api_key="",
             stream=True, temperature=None, max_tokens=None, extra=None) -> Iterator[StreamEvent]:
        if not api_key:
            raise ProviderError("vertex: missing api_key (GCP access token)")
        if not self._project():
            raise ProviderError("vertex: set CLIMS_VERTEX_PROJECT")
        caps = self.capabilities(model)
        body = {
            "anthropic_version": "vertex-2023-10-16",
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

        try:
            data = post_json(self.endpoint(model),
                             {"Authorization": f"Bearer {api_key}"}, body)
        except HTTPError as e:
            yield StreamEvent.failure(f"vertex HTTP {e.status}: {e.body[:300]}")
            return
        for block in data.get("content", []) or []:
            t = block.get("type")
            if t == "text":
                yield StreamEvent.text_delta(block.get("text", ""))
            elif t == "tool_use":
                yield StreamEvent.tool(block.get("id", ""), block.get("name", ""), block.get("input", {}) or {})
        usage = data.get("usage") or {}
        if usage:
            yield StreamEvent.usage(usage.get("input_tokens", 0), usage.get("output_tokens", 0))
        yield StreamEvent.finished(data.get("stop_reason", "end_turn"))
