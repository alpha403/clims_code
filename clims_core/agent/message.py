"""Normalized message model — the heart of model-agnosticism.

Every provider adapter converts to/from these types, so the agent loop, tools,
server, and CLI never deal with provider-specific wire formats.

Roles (normalized):
  - "system"    : system prompt (usually hoisted out by adapters)
  - "user"      : human / caller input
  - "assistant" : model output (text, thinking, tool_use)
  - "tool"      : tool results (adapters map this to each API's convention)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Union

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class TextBlock:
    text: str
    type: Literal["text"] = "text"


@dataclass
class ThinkingBlock:
    """Extended reasoning, when the model/provider exposes it."""
    text: str
    signature: str | None = None  # some providers sign thinking blocks
    type: Literal["thinking"] = "thinking"


@dataclass
class ImageBlock:
    """Image input. `data` is base64 (no data: prefix); `media_type` like image/png."""
    media_type: str
    data: str
    type: Literal["image"] = "image"


@dataclass
class ToolUseBlock:
    """A model's request to call a tool."""
    id: str
    name: str
    input: dict
    type: Literal["tool_use"] = "tool_use"


@dataclass
class ToolResultBlock:
    """The result of executing a tool, fed back to the model. `images` lets a tool
    return actual images (each {"media_type","data"=base64}) for vision models."""
    tool_use_id: str
    content: str
    is_error: bool = False
    images: list = field(default_factory=list)
    type: Literal["tool_result"] = "tool_result"


ContentBlock = Union[
    TextBlock, ThinkingBlock, ImageBlock, ToolUseBlock, ToolResultBlock
]


@dataclass
class Message:
    role: Role
    content: list[ContentBlock] = field(default_factory=list)

    # ---- ergonomic constructors -------------------------------------------------
    @classmethod
    def user(cls, text: str) -> "Message":
        return cls(role="user", content=[TextBlock(text)])

    @classmethod
    def assistant(cls, text: str) -> "Message":
        return cls(role="assistant", content=[TextBlock(text)])

    @classmethod
    def system(cls, text: str) -> "Message":
        return cls(role="system", content=[TextBlock(text)])

    @classmethod
    def tool_results(cls, results: list[ToolResultBlock]) -> "Message":
        return cls(role="tool", content=list(results))

    # ---- helpers ---------------------------------------------------------------
    def text(self) -> str:
        """Concatenated text of all TextBlocks (ignores thinking/tool blocks)."""
        return "".join(b.text for b in self.content if isinstance(b, TextBlock))

    def tool_uses(self) -> list[ToolUseBlock]:
        return [b for b in self.content if isinstance(b, ToolUseBlock)]

    def to_dict(self) -> dict:
        """Plain-dict form for persistence/transport (NOT a provider wire format)."""
        return {
            "role": self.role,
            "content": [_block_to_dict(b) for b in self.content],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Message":
        return cls(
            role=d["role"],
            content=[_block_from_dict(b) for b in d.get("content", [])],
        )


# ---- (de)serialization -----------------------------------------------------------

_BLOCK_TYPES = {
    "text": TextBlock,
    "thinking": ThinkingBlock,
    "image": ImageBlock,
    "tool_use": ToolUseBlock,
    "tool_result": ToolResultBlock,
}


def _block_to_dict(b: ContentBlock) -> dict:
    return dict(b.__dict__)


def _block_from_dict(d: dict) -> ContentBlock:
    kind = d.get("type", "text")
    cls = _BLOCK_TYPES.get(kind, TextBlock)
    data = {k: v for k, v in d.items() if k != "type"}
    return cls(**data)
