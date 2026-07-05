"""Provider layer — one interface, many model APIs behind it.

`get_provider(name)` returns a singleton adapter. Adding a model API = drop a new
module here and register it in `_REGISTRY`.
"""
from __future__ import annotations

from clims_core.providers.base import Provider, StreamEvent, ModelCapabilities, ToolSchema


def get_provider(name: str) -> Provider:
    name = (name or "").lower().strip()
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown provider {name!r}. Known: {', '.join(sorted(_REGISTRY))}"
        )
    if _INSTANCES.get(name) is None:
        _INSTANCES[name] = _REGISTRY[name]()
    return _INSTANCES[name]


def available_providers() -> list[str]:
    return sorted(_REGISTRY)


def _make_deepseek() -> Provider:
    from clims_core.providers.deepseek import DeepSeekProvider
    return DeepSeekProvider()


def _make_anthropic() -> Provider:
    from clims_core.providers.anthropic import AnthropicProvider
    return AnthropicProvider()


def _make_openai() -> Provider:
    from clims_core.providers.openai import OpenAIProvider
    return OpenAIProvider()


def _make_ollama() -> Provider:
    from clims_core.providers.ollama import OllamaProvider
    return OllamaProvider()


def _make_gemini() -> Provider:
    from clims_core.providers.gemini import GeminiProvider
    return GeminiProvider()


def _make_bedrock() -> Provider:
    from clims_core.providers.bedrock import BedrockAnthropicProvider
    return BedrockAnthropicProvider()


def _make_vertex() -> Provider:
    from clims_core.providers.vertex import VertexAnthropicProvider
    return VertexAnthropicProvider()


# name -> factory (lazy import so an adapter's deps/errors don't break the rest)
_REGISTRY: dict[str, callable] = {
    "deepseek": _make_deepseek,
    "anthropic": _make_anthropic,
    "openai": _make_openai,
    "ollama": _make_ollama,
    "gemini": _make_gemini,
    "bedrock": _make_bedrock,
    "vertex": _make_vertex,
}
_INSTANCES: dict[str, Provider | None] = {k: None for k in _REGISTRY}

__all__ = [
    "Provider",
    "StreamEvent",
    "ModelCapabilities",
    "ToolSchema",
    "get_provider",
    "available_providers",
]
