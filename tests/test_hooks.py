"""Hook system tests — uses cross-platform `python -c` hook commands."""
import sys
from pathlib import Path

from clims_core.agent.loop import Agent
from clims_core.agent.message import Message, ToolResultBlock
from clims_core.agent.runtime import ToolRuntime
from clims_core.hooks import HookRunner
from clims_core.permissions.policy import PermissionMode, PermissionPolicy
from clims_core.providers.base import StreamEvent
from clims_core.tools import default_tools, tool_map
from clims_core.tools.base import ToolContext

from tests.fake_provider import FakeProvider

PY = sys.executable


def _runtime(tmp_path, hooks_cfg):
    hooks = HookRunner(hooks_cfg, cwd=tmp_path)
    return ToolRuntime(tool_map(default_tools()),
                       PermissionPolicy(mode=PermissionMode.BYPASS),
                       ToolContext(cwd=tmp_path), hooks=hooks)


def test_pretooluse_blocks_a_tool(tmp_path: Path):
    # hook exits 2 -> block, for any bash call
    cfg = {"PreToolUse": [{"matcher": "bash",
                           "hooks": [{"type": "command",
                                      "command": f'{PY} -c "import sys; sys.exit(2)"'}]}]}
    scripts = [
        [StreamEvent.tool("c1", "bash", {"command": "echo hi"}), StreamEvent.finished("tool_use")],
        [StreamEvent.text_delta("done"), StreamEvent.finished("end_turn")],
    ]
    agent = Agent(provider=FakeProvider(scripts), model="fake", api_key="x",
                  runtime=_runtime(tmp_path, cfg))
    res = agent.send([Message.user("run echo")], lambda e: None)
    # the tool result fed back must be an error mentioning the block
    block = res.messages[2].content[0]
    assert isinstance(block, ToolResultBlock) and block.is_error
    assert "PreToolUse" in block.content


def test_pretooluse_allows_when_matcher_misses(tmp_path: Path):
    # hook only targets 'write', but the call is 'read' -> not blocked
    (tmp_path / "f.txt").write_text("hello", encoding="utf-8")
    cfg = {"PreToolUse": [{"matcher": "write",
                           "hooks": [{"type": "command", "command": f'{PY} -c "import sys; sys.exit(2)"'}]}]}
    scripts = [
        [StreamEvent.tool("c1", "read", {"path": "f.txt"}), StreamEvent.finished("tool_use")],
        [StreamEvent.text_delta("ok"), StreamEvent.finished("end_turn")],
    ]
    agent = Agent(provider=FakeProvider(scripts), model="fake", api_key="x",
                  runtime=_runtime(tmp_path, cfg))
    res = agent.send([Message.user("read it")], lambda e: None)
    block = res.messages[2].content[0]
    assert not block.is_error and "hello" in block.content


def test_userpromptsubmit_blocks(tmp_path: Path):
    cfg = {"UserPromptSubmit": [{"matcher": "*",
                                 "hooks": [{"type": "command", "command": f'{PY} -c "import sys; sys.exit(2)"'}]}]}
    scripts = [[StreamEvent.text_delta("should not run"), StreamEvent.finished("end_turn")]]
    provider = FakeProvider(scripts)
    agent = Agent(provider=provider, model="fake", api_key="x",
                  runtime=_runtime(tmp_path, cfg))
    res = agent.send([Message.user("hi")], lambda e: None)
    assert res.stop_reason == "blocked"
    assert len(provider.calls) == 0  # model never called


def test_userpromptsubmit_injects_context(tmp_path: Path):
    # hook prints JSON additionalContext on stdout, exit 0
    code = "import json; print(json.dumps({'additionalContext': 'REMEMBER: be brief'}))"
    cfg = {"UserPromptSubmit": [{"matcher": "*",
                                 "hooks": [{"type": "command", "command": f'{PY} -c "{code}"'}]}]}
    scripts = [[StreamEvent.text_delta("ok"), StreamEvent.finished("end_turn")]]
    provider = FakeProvider(scripts)
    agent = Agent(provider=provider, model="fake", api_key="x",
                  runtime=_runtime(tmp_path, cfg))
    agent.send([Message.user("hi")], lambda e: None)
    # the injected context must appear in the messages the model received
    sent = provider.calls[0]
    assert any("REMEMBER: be brief" in m.text() for m in sent)
