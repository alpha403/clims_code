"""A scripted in-memory Provider for testing the loop/runtime without network.

Emits a predefined sequence of StreamEvents per turn and records the messages it
received, so tests can assert that tool results were fed back to the model.
"""
from __future__ import annotations

from typing import Iterator

from clims_core.providers.base import Provider, StreamEvent, ModelCapabilities, ToolSchema
from clims_core.agent.message import Message


class FakeProvider(Provider):
    name = "fake"

    def __init__(self, scripts: list[list[StreamEvent]], context_window: int = 8192):
        # scripts[i] = events to emit on the i-th chat() call
        self.scripts = scripts
        self.calls: list[list[Message]] = []
        self._context_window = context_window

    def capabilities(self, model: str) -> ModelCapabilities:
        return ModelCapabilities(context_window=self._context_window)

    def chat(self, *, model, messages, tools=None, system=None, api_key,
             stream=True, temperature=None, max_tokens=None, extra=None
             ) -> Iterator[StreamEvent]:
        self.calls.append(list(messages))
        idx = len(self.calls) - 1
        events = self.scripts[idx] if idx < len(self.scripts) else [StreamEvent.finished("end_turn")]
        for ev in events:
            yield ev
