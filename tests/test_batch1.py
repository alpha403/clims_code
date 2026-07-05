"""Batch 1: microcompaction, styles, plan tool, model switch, /auto, /hooks."""
from clims_cli.repl import _handle_slash
from clims_core.agent.compaction import microcompact, estimate_tokens
from clims_core.agent.loop import Agent
from clims_core.agent.message import Message, ToolResultBlock
from clims_core.agent.runtime import ToolRuntime
from clims_core.config import Config
from clims_core.hooks import HookRunner
from clims_core.permissions.policy import PermissionMode, PermissionPolicy
from clims_core.styles import style_suffix, style_names
from clims_core.tools import default_tools, tool_map, ExitPlanModeTool
from clims_core.tools.base import ToolContext

from tests.fake_provider import FakeProvider


def _agent(hooks=None):
    rt = ToolRuntime(tool_map(default_tools()),
                     PermissionPolicy(mode=PermissionMode.DEFAULT), ToolContext(), hooks=hooks)
    return Agent(provider=FakeProvider([]), model="deepseek-chat", api_key="k", runtime=rt)


def test_microcompact_shrinks_old_tool_output():
    msgs = []
    for i in range(12):
        msgs.append(Message.user(f"q{i}"))
        msgs.append(Message.assistant(f"a{i}"))
        msgs.append(Message.tool_results([ToolResultBlock(f"t{i}", "X" * 5000)]))
    before = estimate_tokens(msgs)
    out = microcompact(msgs, keep_recent=6, max_tool_chars=2000)
    after = estimate_tokens(out)
    assert after < before
    assert len(out) == len(msgs)  # no messages dropped


def test_styles():
    assert "concise" in style_names()
    assert "concise" in style_suffix("concise").lower()
    assert style_suffix(None) == "" and style_suffix("nope") == ""


def test_plan_tool_records_plan():
    ctx = ToolContext()
    res = ExitPlanModeTool().run({"plan": "1. do X\n2. do Y"}, ctx)
    assert not res.is_error and "do X" in res.content
    assert ctx.jobs["__plan__"].startswith("1. do X")
    assert ExitPlanModeTool().run({}, ctx).is_error


def test_model_switch_command():
    a = _agent()
    cfg = Config(provider="deepseek", model="deepseek-chat")
    _handle_slash("/model deepseek-reasoner", cfg, a, [], {"in": 0, "out": 0})
    assert a.model == "deepseek-reasoner" and cfg.model == "deepseek-reasoner"


def test_auto_toggle():
    a = _agent()
    assert a.runtime.policy.mode == PermissionMode.DEFAULT
    _handle_slash("/auto", Config(), a, [], {"in": 0, "out": 0})
    assert a.runtime.policy.mode == PermissionMode.ACCEPT_EDITS
    _handle_slash("/auto", Config(), a, [], {"in": 0, "out": 0})
    assert a.runtime.policy.mode == PermissionMode.DEFAULT


def test_hooks_command(capsys):
    hooks = HookRunner({"PreToolUse": [{"matcher": "*", "hooks": []}]})
    a = _agent(hooks=hooks)
    _handle_slash("/hooks", Config(), a, [], {"in": 0, "out": 0})
    assert "PreToolUse" in capsys.readouterr().out


def test_plan_tool_in_default_set():
    assert "exit_plan_mode" in tool_map(default_tools())
