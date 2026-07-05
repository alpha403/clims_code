"""Context auto-compaction tests."""
from clims_core.agent.compaction import (
    estimate_tokens, needs_compaction, compact, _safe_split,
)
from clims_core.agent.loop import Agent
from clims_core.agent.message import Message, TextBlock, ToolUseBlock, ToolResultBlock
from clims_core.agent.runtime import ToolRuntime
from clims_core.permissions.policy import PermissionMode, PermissionPolicy
from clims_core.providers.base import StreamEvent
from clims_core.tools import default_tools, tool_map
from clims_core.tools.base import ToolContext

from tests.fake_provider import FakeProvider


def _big_history(n=10, size=4000):
    msgs = []
    for i in range(n):
        msgs.append(Message.user("U" * size + f" turn{i}"))
        msgs.append(Message.assistant("A" * size))
    return msgs


def test_estimate_and_needs():
    h = _big_history(5, 4000)
    assert estimate_tokens(h) > 0
    assert needs_compaction(h, context_window=1000)
    assert not needs_compaction(h, context_window=10_000_000)


def test_safe_split_lands_on_user_boundary():
    msgs = [
        Message.user("u1"),
        Message(role="assistant", content=[ToolUseBlock("c1", "bash", {"command": "ls"})]),
        Message.tool_results([ToolResultBlock("c1", "out")]),
        Message.user("u2"),
        Message.assistant("done"),
    ]
    split = _safe_split(msgs, keep_recent=2)
    # must not start the kept slice on a 'tool' message
    assert msgs[split].role == "user"


def test_compact_replaces_old_with_summary():
    h = _big_history(8, 4000)
    out, did = compact(h, summarizer=lambda ms: "SUMMARY", context_window=2000, keep_recent=4)
    assert did
    assert "SUMMARY" in out[0].text()
    assert len(out) < len(h)
    # recent turns preserved verbatim at the tail
    assert out[-1].text() == h[-1].text()


def test_compact_noop_when_small():
    h = [Message.user("hi"), Message.assistant("hello")]
    out, did = compact(h, summarizer=lambda ms: "X", context_window=100000)
    assert not did and out == h


def test_agent_triggers_compaction_before_model_call():
    # tiny window forces compaction; injected summarizer avoids extra model calls
    provider = FakeProvider(
        [[StreamEvent.text_delta("ok"), StreamEvent.finished("end_turn")]],
        context_window=500,
    )
    rt = ToolRuntime(tool_map(default_tools()),
                     PermissionPolicy(mode=PermissionMode.BYPASS), ToolContext())
    agent = Agent(provider=provider, model="fake", api_key="x", runtime=rt,
                  auto_compact=True, summarizer=lambda ms: "COMPACTED SUMMARY")
    agent.send(_big_history(8, 4000), lambda e: None)
    # the messages the model actually received must begin with the summary
    sent = provider.calls[0]
    assert "COMPACTED SUMMARY" in sent[0].text()
    assert len(sent) < 16
