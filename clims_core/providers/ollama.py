"""Ollama provider — local models via Ollama's OpenAI-compatible endpoint.

No API key required (local). Defaults to http://localhost:11434/v1, overridable
with OLLAMA_HOST. Demonstrates the engine running fully offline / on-device.
"""
from __future__ import annotations

import os
from typing import Iterator

from clims_core.providers.base import StreamEvent
from clims_core.providers.deepseek import DeepSeekProvider


class OllamaProvider(DeepSeekProvider):
    name = "ollama"

    def __init__(self):
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.base_url = host.rstrip("/") + "/v1"

    def _headers(self, api_key: str) -> dict:
        return {}  # local server, no auth

    def chat(self, **kw) -> Iterator[StreamEvent]:
        # local Ollama needs no key; supply a placeholder so the BYOK guard passes
        kw["api_key"] = kw.get("api_key") or "ollama-local"
        yield from super().chat(**kw)
