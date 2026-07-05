"""Provider interface + the normalized streaming event model.

A Provider turns normalized Messages into provider wire format, makes the HTTP
call, and yields a stream of normalized StreamEvents back. The agent loop only
ever sees StreamEvents — never a provider's raw JSON.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, Literal

from clims_core.agent.message import Message


@dataclass
class ToolSchema:
    """A tool definition advertised to the model (provider-neutral)."""
    name: str
    description: str
    input_schema: dict  # JSON Schema object


@dataclass
class ModelCapabilities:
    context_window: int = 8192
    max_output: int = 4096
    supports_tools: bool = True
    supports_vision: bool = False
    supports_thinking: bool = False
    supports_prompt_cache: bool = False
    supports_streaming: bool = True


EventType = Literal[
    "text_delta",          # incremental assistant text
    "thinking_delta",      # incremental reasoning text
    "tool_use",            # a complete tool call (id/name/input)
    "usage",               # token accounting
    "done",                # turn finished (stop_reason)
    "error",               # provider/transport error
    # agent-level events (emitted by the loop/runtime, not providers):
    "permission_request",  # a tool call is awaiting approval
    "tool_result",         # a tool finished executing
]


@dataclass
class StreamEvent:
    type: EventType
    # text/thinking deltas:
    text: str = ""
    # tool_use:
    tool_id: str = ""
    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)
    # usage:
    input_tokens: int = 0
    output_tokens: int = 0
    # done:
    stop_reason: str = ""
    # error / tool_result content:
    message: str = ""
    # tool_result:
    is_error: bool = False

    # ---- convenience builders ----
    @staticmethod
    def text_delta(text: str) -> "StreamEvent":
        return StreamEvent(type="text_delta", text=text)

    @staticmethod
    def thinking_delta(text: str) -> "StreamEvent":
        return StreamEvent(type="thinking_delta", text=text)

    @staticmethod
    def tool(tool_id: str, name: str, input: dict) -> "StreamEvent":
        return StreamEvent(type="tool_use", tool_id=tool_id, tool_name=name, tool_input=input)

    @staticmethod
    def usage(input_tokens: int, output_tokens: int) -> "StreamEvent":
        return StreamEvent(type="usage", input_tokens=input_tokens, output_tokens=output_tokens)

    @staticmethod
    def finished(stop_reason: str) -> "StreamEvent":
        return StreamEvent(type="done", stop_reason=stop_reason)

    @staticmethod
    def failure(message: str) -> "StreamEvent":
        return StreamEvent(type="error", message=message)

    @staticmethod
    def permission(tool_id: str, name: str, input: dict) -> "StreamEvent":
        return StreamEvent(type="permission_request", tool_id=tool_id, tool_name=name, tool_input=input)

    @staticmethod
    def tool_done(tool_id: str, name: str, content: str, is_error: bool) -> "StreamEvent":
        return StreamEvent(type="tool_result", tool_id=tool_id, tool_name=name, message=content, is_error=is_error)


class ProviderError(Exception):
    """Raised for non-retryable provider/transport failures."""


def stream_with_retry(make_stream, max_retries: int = 2, base_delay: float = 1.0):
    """Wrap a streaming attempt with transient-failure retries.

    `make_stream` must return a FRESH iterator of StreamEvents per call (i.e. a
    new HTTP request). We retry only while nothing "productive" (model text or a
    tool call) has been emitted yet — once real output is committed we can't
    safely restart, so we surface the error instead. This turns transient socket
    timeouts / 429s / 5xx at the start of a turn into a silent retry rather than
    a crash.
    """
    import time

    attempt = 0
    while True:
        productive = False
        try:
            for ev in make_stream():
                if ev.type in ("text_delta", "thinking_delta", "tool_use"):
                    productive = True
                if ev.type == "error" and not productive and attempt < max_retries:
                    break  # swallow and retry
                yield ev
            else:
                return  # generator finished normally
            # fell through via break -> retry
        except Exception as e:  # network/socket/timeout raised mid-attempt
            if productive or attempt >= max_retries:
                yield StreamEvent.failure(f"{type(e).__name__}: {e}")
                return
        attempt += 1
        time.sleep(base_delay * (2 ** (attempt - 1)))


class Provider(ABC):
    name: str = "base"

    @abstractmethod
    def chat(
        self,
        *,
        model: str,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        system: str | None = None,
        api_key: str,
        stream: bool = True,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra: dict | None = None,
    ) -> Iterator[StreamEvent]:
        """Yield normalized StreamEvents for one model turn."""
        raise NotImplementedError

    @abstractmethod
    def capabilities(self, model: str) -> ModelCapabilities:
        raise NotImplementedError
