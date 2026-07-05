"""Image input — build a multimodal user message from image file(s).

Reads images from disk, base64-encodes them, and produces a Message with
ImageBlock(s) the provider adapters already know how to wire (Anthropic image
blocks, OpenAI image_url, Gemini inlineData).
"""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from clims_core.agent.message import Message, TextBlock, ImageBlock


def _media_type(path: Path) -> str:
    mt, _ = mimetypes.guess_type(str(path))
    if mt and mt.startswith("image/"):
        return mt
    return "image/png"


def build_image_message(text: str, image_paths: list[str], cwd: Path | None = None) -> Message:
    cwd = cwd or Path.cwd()
    blocks = []
    if text:
        blocks.append(TextBlock(text))
    for ref in image_paths:
        p = Path(ref)
        target = p if p.is_absolute() else (cwd / p)
        if not target.is_file():
            blocks.append(TextBlock(f"[image not found: {ref}]"))
            continue
        data = base64.b64encode(target.read_bytes()).decode("ascii")
        blocks.append(ImageBlock(media_type=_media_type(target), data=data))
    return Message(role="user", content=blocks or [TextBlock(text)])
