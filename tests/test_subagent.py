"""Subagent tool tests."""
from clims_core.agent.loop import Agent
from clims_core.agent.message import Message
from clims_core.agent.runtime import ToolRuntime
from clims_core.agent.subagent import SubagentTool
from clims_core.permissions.policy import PermissionMode, PermissionPolicy
from clims_core.providers.base import StreamEvent
from clims_core.tools import default_tools, tool_map
from clims_core.tools.base import ToolContext

from tests.fake_provider import FakeProvider


def test_subagent_delegates_to_spawn():
    seen = {}

    def spawn(task, agent_type=None):
        seen["task"] = task
        return f"handled: {task}"

    tool = SubagentTool(spawn)
    res = tool.run({"task": "do X"}, ToolContext())
    assert res.content == "handled: do X" and not res.is_error
    assert seen["task"] == "do X"


def test_subagent_requires_task():
    res = SubagentTool(lambda t: "x").run({}, ToolContext())
    assert res.is_error


def test_subagent_runs_a_real_child_agent():
    # child agent returns text via a fake provider
    provider = FakeProvider([
        [StreamEvent.text_delta("CHILD ANSWER"), StreamEvent.finished("end_turn")],
    ])

    def spawn(task, agent_type=None):
        rt = ToolRuntime(tool_map(default_tools()),
                         PermissionPolicy(mode=PermissionMode.BYPASS), ToolContext())
        child = Agent(provider=provider, model="fake", api_key="x", runtime=rt)
        r = child.send([Message.user(task)], lambda e: None)
        return r.messages[-1].text()

    tool = SubagentTool(spawn)
    res = tool.run({"task": "research the thing"}, ToolContext())
    assert "CHILD ANSWER" in res.content
    # child actually received the delegated task
    assert any("research the thing" in m.text() for m in provider.calls[0])


def test_main_agent_invokes_subagent_end_to_end():
    # main agent calls subagent tool; child returns; main finishes
    provider = FakeProvider([
        # main turn 1: call subagent
        [StreamEvent.tool("c1", "subagent", {"task": "compute 2+2"}),
         StreamEvent.finished("tool_use")],
        # child turn: answer
        [StreamEvent.text_delta("the answer is 4"), StreamEvent.finished("end_turn")],
        # main turn 2: final
        [StreamEvent.text_delta("Subagent said: 4"), StreamEvent.finished("end_turn")],
    ])

    def spawn(task, agent_type=None):
        rt = ToolRuntime(tool_map(default_tools()),
                         PermissionPolicy(mode=PermissionMode.BYPASS), ToolContext())
        child = Agent(provider=provider, model="fake", api_key="x", runtime=rt)
        return child.send([Message.user(task)], lambda e: None).messages[-1].text()

    tools = default_tools() + [SubagentTool(spawn)]
    rt = ToolRuntime(tool_map(tools), PermissionPolicy(mode=PermissionMode.BYPASS), ToolContext())
    main = Agent(provider=provider, model="fake", api_key="x", runtime=rt)
    res = main.send([Message.user("delegate this")], lambda e: None)
    assert "Subagent said: 4" in res.messages[-1].text()
