"""Vision sidecar — send image(s) + a question to a vision-capable provider and
get a text answer back.

Lets a text-only brain (e.g. DeepSeek) "see" by delegating just the image to a
vision model (Gemini/OpenAI/Claude/Ollama) through the same provider abstraction.
Reuses the ImageBlock the adapters already serialize.
"""
from __future__ import annotations

from clims_core.agent.message import Message, TextBlock, ImageBlock
from clims_core.providers import get_provider

VISION_SYSTEM = (
    "You are a precise vision assistant. Look at the image(s) and answer the question "
    "directly and concisely. If asked to extract or read text, transcribe it exactly. "
    "Describe only what is actually visible; do not invent details."
)


def analyze(provider_name: str, model: str, api_key: str,
            images: list[tuple[str, str]], question: str,
            temperature: float = 0.0) -> str:
    """images: list of (media_type, base64_data). Returns the model's text answer."""
    provider = get_provider(provider_name)
    blocks: list = [ImageBlock(media_type=mt, data=data) for mt, data in images]
    blocks.append(TextBlock(question or "Describe this image in detail."))
    msg = Message(role="user", content=blocks)

    parts: list[str] = []
    for ev in provider.chat(
        model=model,
        messages=[msg],
        tools=[],
        system=VISION_SYSTEM,
        api_key=api_key,
        stream=True,
        temperature=temperature,
        max_tokens=None,
    ):
        if ev.type == "text_delta":
            parts.append(ev.text)
        elif ev.type == "error":
            raise RuntimeError(ev.message or "vision provider error")
    return "".join(parts).strip()
