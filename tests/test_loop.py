"""End-to-end agent loop test with a scripted provider — no network.

Proves: model tool_call -> tool executes -> result fed back -> model finishes.
"""
from pathlib import Path

from clims_core.agent.loop import Agent
from clims_core.agent.message import Message, ToolResultBlock
from clims_core.agent.runtime import ToolRuntime
from clims_core.permissions.policy import PermissionMode, PermissionPolicy
from clims_core.providers.base import StreamEvent
from clims_core.tools import default_tools, tool_map
from clims_core.tools.base import ToolContext

from tests.fake_provider import FakeProvider


def test_loop_executes_tool_and_feeds_result_back(tmp_path: Path):
    target = tmp_path / "hello.txt"
    # turn 1: model asks to write a file; turn 2: model says done
    scripts = [
        [
            StreamEvent.text_delta("I'll create the file."),
            StreamEvent.tool("call-1", "write",
                             {"path": str(target), "content": "hi there\n"}),
            StreamEvent.finished("tool_use"),
        ],
        [
            StreamEvent.text_delta("Done — file created."),
            StreamEvent.usage(10, 5),
            StreamEvent.finished("end_turn"),
        ],
    ]
    provider = FakeProvider(scripts)
    tools = default_tools()
    policy = PermissionPolicy(mode=PermissionMode.BYPASS)
    runtime = ToolRuntime(tool_map(tools), policy, ToolContext(cwd=tmp_path))
    agent = Agent(provider=provider, model="fake", api_key="x", runtime=runtime)

    events = []
    result = agent.send([Message.user("create hello.txt")], events.append)

    # file actually written by the tool
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "hi there\n"

    # the loop made a second call, and that call saw the tool result
    assert len(provider.calls) == 2
    second_call_msgs = provider.calls[1]
    tool_msgs = [m for m in second_call_msgs if m.role == "tool"]
    assert tool_msgs, "tool result was not fed back to the model"
    block = tool_msgs[0].content[0]
    assert isinstance(block, ToolResultBlock)
    assert not block.is_error

    # final assistant text present
    assert "Done" in result.messages[-1].text()
    assert result.input_tokens == 10 and result.output_tokens == 5
    # a tool_result event was emitted to the sink
    assert any(e.type == "tool_result" for e in events)


def test_plan_mode_denies_mutation(tmp_path: Path):
    target = tmp_path / "blocked.txt"
    scripts = [
        [
            StreamEvent.tool("c1", "write", {"path": str(target), "content": "x"}),
            StreamEvent.finished("tool_use"),
        ],
        [StreamEvent.text_delta("ok"), StreamEvent.finished("end_turn")],
    ]
    provider = FakeProvider(scripts)
    tools = default_tools()
    policy = PermissionPolicy(mode=PermissionMode.PLAN)  # read-only
    runtime = ToolRuntime(tool_map(tools), policy, ToolContext(cwd=tmp_path))
    agent = Agent(provider=provider, model="fake", api_key="x", runtime=runtime)

    agent.send([Message.user("write a file")], lambda e: None)
    # write must have been denied -> file not created
    assert not target.exists()
    # the tool result fed back must be an error
    block = provider.calls[1][-1].content[0]
    assert block.is_error
