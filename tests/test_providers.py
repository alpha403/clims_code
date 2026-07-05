"""Provider registry + OpenAI-compatible subclass wiring tests (no network)."""
from clims_core.agent.message import Message
from clims_core.providers import get_provider, available_providers
from clims_core.providers.openai import OpenAIProvider
from clims_core.providers.ollama import OllamaProvider


def test_all_providers_registered():
    provs = available_providers()
    for name in ("deepseek", "anthropic", "openai", "ollama"):
        assert name in provs
        assert get_provider(name) is not None


def test_openai_reuses_openai_wire_format():
    p = OpenAIProvider()
    assert p.base_url == "https://api.openai.com/v1"
    msgs = p._messages_wire([Message.user("hi")], system="sys")
    assert msgs[0] == {"role": "system", "content": "sys"}
    assert msgs[1]["role"] == "user"


def test_ollama_no_auth_header_and_key_optional():
    p = OllamaProvider()
    assert p._headers("") == {}  # local, no auth
    # ollama injects a placeholder key so the BYOK guard passes; just ensure the
    # generator is constructable without raising on missing key
    gen = p.chat(model="llama3.1", messages=[Message.user("hi")], api_key="")
    assert gen is not None


def test_capabilities_lookup_and_fallback():
    p = get_provider("openai")
    caps = p.capabilities("gpt-4o")
    assert caps.context_window == 128000 and caps.supports_vision
    # unknown model -> conservative default, not a crash
    fallback = p.capabilities("some-future-model")
    assert fallback.supports_tools is True
