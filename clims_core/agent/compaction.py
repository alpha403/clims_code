"""Context auto-compaction.

When a conversation approaches the model's context window, replace the oldest
turns with a concise summary, preserving recent turns verbatim. Splitting always
happens on a clean user-message boundary so we never orphan a tool_use/tool_result
pair (which providers reject).

Token estimate is a cheap chars/4 heuristic — good enough to decide *when* to
compact without a tokenizer dependency (keeps the engine zero-dep).
"""
from __future__ import annotations

from typing import Callable

from clims_core.agent.message import Message, TextBlock, ToolResultBlock

Summarizer = Callable[[list[Message]], str]


def microcompact(messages: list[Message], keep_recent: int = 8,
                 max_tool_chars: int = 2000) -> list[Message]:
    """Cheap, lossless-ish trim: shorten large tool outputs in OLD turns (keeping
    recent ones intact). Runs before full summarization to delay it. Does not drop
    messages, so tool_use/tool_result pairing stays valid."""
    cutoff = len(messages) - keep_recent
    if cutoff <= 0:
        return messages
    out = []
    for i, m in enumerate(messages):
        if i < cutoff and m.role == "tool":
            new_blocks = []
            for b in m.content:
                if isinstance(b, ToolResultBlock) and len(b.content) > max_tool_chars:
                    new_blocks.append(ToolResultBlock(
                        b.tool_use_id,
                        b.content[:200] + f"\n…[older tool output elided, "
                                          f"{len(b.content) - 200} chars]",
                        b.is_error))
                else:
                    new_blocks.append(b)
            out.append(Message(role="tool", content=new_blocks))
        else:
            out.append(m)
    return out


def _text_of(messages: list[Message]) -> str:
    parts = []
    for m in messages:
        for b in m.content:
            parts.append(getattr(b, "text", "") or "")
            parts.append(getattr(b, "content", "") or "")  # tool results
            inp = getattr(b, "input", None)
            if inp:
                parts.append(str(inp))
    return "".join(parts)


# optional precise tokenizer; falls back to a chars/4 heuristic if unavailable
try:
    import tiktoken
    _ENC = tiktoken.get_encoding("cl100k_base")
except Exception:
    _ENC = None


def estimate_tokens(messages: list[Message]) -> int:
    text = _text_of(messages)
    if _ENC is not None:
        try:
            return len(_ENC.encode(text, disallowed_special=()))
        except Exception:
            pass
    return len(text) // 4


import os as _os

# how full the context may get before we compact. Kept conservative (well under the
# window) because quality degrades as context fills ("context rot"), and because the
# system prompt + tool schemas (~3-4k tokens) aren't included in the message estimate.
# Override with CLIMS_CONTEXT_TRIGGER (e.g. 0.5 for leaner, 0.7 to delay compaction).
def _trigger(trigger_frac: float | None) -> float:
    if trigger_frac is not None:
        return trigger_frac
    try:
        v = float(_os.environ.get("CLIMS_CONTEXT_TRIGGER", "0.6"))
    except (TypeError, ValueError):
        v = 0.6
    return min(0.9, max(0.3, v))


def needs_compaction(messages: list[Message], context_window: int,
                     trigger_frac: float | None = None) -> bool:
    if context_window <= 0:
        return False
    return estimate_tokens(messages) >= context_window * _trigger(trigger_frac)


def _safe_split(messages: list[Message], keep_recent: int) -> int:
    """Index where the 'recent' (kept) slice begins — the latest user-message
    boundary at or before len-keep_recent. Returns 0 if no safe split exists."""
    target = max(1, len(messages) - keep_recent)
    for i in range(min(target, len(messages) - 1), 0, -1):
        if messages[i].role == "user":
            return i
    return 0


def compact(messages: list[Message], summarizer: Summarizer, context_window: int,
            keep_recent: int = 6, trigger_frac: float | None = None) -> tuple[list[Message], bool]:
    """Return (possibly-compacted messages, did_compact)."""
    if not needs_compaction(messages, context_window, trigger_frac):
        return messages, False
    split = _safe_split(messages, keep_recent)
    if split <= 0:
        return messages, False
    older, recent = messages[:split], messages[split:]
    try:
        summary = summarizer(older)
    except Exception:
        return messages, False  # never let compaction break a turn
    if not summary:
        return messages, False
    summary_msg = Message(role="user", content=[
        TextBlock("[Summary of earlier conversation — older turns were compacted "
                  "to fit the context window]\n" + summary)
    ])
    return [summary_msg] + recent, True
