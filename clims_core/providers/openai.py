"""OpenAI provider — reuses the OpenAI-compatible DeepSeek implementation.

The DeepSeek adapter already speaks the OpenAI chat-completions dialect, so the
OpenAI provider is just a different base URL + model registry. This is the payoff
of a clean provider boundary: a new model API in a few lines.
"""
from __future__ import annotations

from clims_core.providers.deepseek import DeepSeekProvider


class OpenAIProvider(DeepSeekProvider):
    name = "openai"
    base_url = "https://api.openai.com/v1"
