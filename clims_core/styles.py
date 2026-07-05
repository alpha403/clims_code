"""Output styles — named system-prompt presets (Claude Code's output styles).

Selectable via config `output_style` or the /style command. Each style is a
suffix appended to the base system prompt to shape tone/format.
"""
from __future__ import annotations

STYLES: dict[str, str] = {
    "default": "",
    "concise": (
        "\n\nOutput style: be maximally concise. Prefer short, direct answers; "
        "skip preamble and restating the question."
    ),
    "explanatory": (
        "\n\nOutput style: explain your reasoning and the why behind actions as you "
        "work, in clear prose suitable for learning."
    ),
    "formal": (
        "\n\nOutput style: use a formal, professional register; complete sentences; "
        "no slang or emoji."
    ),
    "bullet": (
        "\n\nOutput style: structure answers as bullet points and short headings "
        "rather than long paragraphs."
    ),
}


def style_suffix(name: str | None) -> str:
    if not name:
        return ""
    return STYLES.get(name.lower(), "")


def style_names() -> list[str]:
    return sorted(STYLES)
