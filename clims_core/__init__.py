"""clims_core — zero-dependency agentic engine.

Public surface kept small and stable so clims_server and clims_cli (and any
embedder) depend only on these names.
"""
from __future__ import annotations

__version__ = "0.1.0"

from clims_core.agent.message import (
    Message,
    TextBlock,
    ThinkingBlock,
    ImageBlock,
    ToolUseBlock,
    ToolResultBlock,
    ContentBlock,
)
from clims_core.providers.base import (
    Provider,
    StreamEvent,
    ModelCapabilities,
    ToolSchema,
)

__all__ = [
    "__version__",
    "Message",
    "TextBlock",
    "ThinkingBlock",
    "ImageBlock",
    "ToolUseBlock",
    "ToolResultBlock",
    "ContentBlock",
    "Provider",
    "StreamEvent",
    "ModelCapabilities",
    "ToolSchema",
]
