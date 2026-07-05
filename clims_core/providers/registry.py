"""Model capability registry.

Maps (provider, model) -> ModelCapabilities. Drives /model, GET /v1/models, and
context-window-aware compaction. Unknown models fall back to conservative
defaults so a brand-new model id still works (just without precise metadata).
"""
from __future__ import annotations

from clims_core.providers.base import ModelCapabilities

# provider -> model id -> capabilities
_TABLE: dict[str, dict[str, ModelCapabilities]] = {
    "deepseek": {
        # deepseek-chat / deepseek-reasoner are aliases for deepseek-v4-flash:
        # 1M-token context window (per api-docs.deepseek.com).
        "deepseek-chat": ModelCapabilities(
            context_window=1000000, max_output=65536,
            supports_tools=True, supports_vision=False, supports_thinking=False,
            supports_prompt_cache=True, supports_streaming=True,
        ),
        "deepseek-reasoner": ModelCapabilities(
            context_window=1000000, max_output=65536,
            supports_tools=True, supports_vision=False, supports_thinking=True,
            supports_prompt_cache=True, supports_streaming=True,
        ),
        "deepseek-v4-flash": ModelCapabilities(
            context_window=1000000, max_output=65536,
            supports_tools=True, supports_vision=False, supports_thinking=True,
            supports_prompt_cache=True, supports_streaming=True,
        ),
    },
    "openai": {
        "gpt-4o": ModelCapabilities(
            context_window=128000, max_output=16384,
            supports_tools=True, supports_vision=True, supports_thinking=False,
            supports_prompt_cache=True, supports_streaming=True,
        ),
        "gpt-4o-mini": ModelCapabilities(
            context_window=128000, max_output=16384,
            supports_tools=True, supports_vision=True, supports_thinking=False,
            supports_prompt_cache=True, supports_streaming=True,
        ),
    },
    "ollama": {
        "llama3.1": ModelCapabilities(
            context_window=128000, max_output=4096,
            supports_tools=True, supports_vision=False, supports_thinking=False,
            supports_prompt_cache=False, supports_streaming=True,
        ),
        "qwen2.5-coder": ModelCapabilities(
            context_window=32000, max_output=4096,
            supports_tools=True, supports_vision=False, supports_thinking=False,
            supports_prompt_cache=False, supports_streaming=True,
        ),
    },
    "gemini": {
        "gemini-2.0-flash": ModelCapabilities(
            context_window=1000000, max_output=8192,
            supports_tools=True, supports_vision=True, supports_thinking=False,
            supports_prompt_cache=True, supports_streaming=True,
        ),
        "gemini-1.5-pro": ModelCapabilities(
            context_window=2000000, max_output=8192,
            supports_tools=True, supports_vision=True, supports_thinking=False,
            supports_prompt_cache=True, supports_streaming=True,
        ),
    },
    "anthropic": {
        "claude-opus-4-8": ModelCapabilities(
            context_window=200000, max_output=32000,
            supports_tools=True, supports_vision=True, supports_thinking=True,
            supports_prompt_cache=True, supports_streaming=True,
        ),
        "claude-sonnet-4-6": ModelCapabilities(
            context_window=200000, max_output=64000,
            supports_tools=True, supports_vision=True, supports_thinking=True,
            supports_prompt_cache=True, supports_streaming=True,
        ),
        "claude-haiku-4-5-20251001": ModelCapabilities(
            context_window=200000, max_output=32000,
            supports_tools=True, supports_vision=True, supports_thinking=False,
            supports_prompt_cache=True, supports_streaming=True,
        ),
    },
}

# conservative fallback for unknown models
_DEFAULT = ModelCapabilities(
    context_window=32000, max_output=4096,
    supports_tools=True, supports_vision=False, supports_thinking=False,
    supports_prompt_cache=False, supports_streaming=True,
)


def lookup(provider: str, model: str) -> ModelCapabilities:
    prov = _TABLE.get(provider, {})
    if model in prov:
        return prov[model]
    # prefix match (e.g. dated suffixes like claude-...-20250101)
    for known, caps in prov.items():
        if model.startswith(known) or known.startswith(model):
            return caps
    return _DEFAULT


def list_models(provider: str | None = None) -> list[dict]:
    out = []
    providers = [provider] if provider else list(_TABLE)
    for prov in providers:
        for model, caps in _TABLE.get(prov, {}).items():
            out.append({
                "provider": prov,
                "model": model,
                "context_window": caps.context_window,
                "max_output": caps.max_output,
                "supports_tools": caps.supports_tools,
                "supports_vision": caps.supports_vision,
                "supports_thinking": caps.supports_thinking,
            })
    return out
