"""Self-configuration: the configure tool changes settings live + persists them."""
import json
from pathlib import Path

from clims_core.permissions.policy import PermissionMode, PermissionPolicy
from clims_core.tools.config_tool import ConfigTool
from clims_core.tools.base import ToolContext


def _local(cwd):
    p = cwd / ".clims" / "settings.local.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def test_allow_rule_applied_live_and_persisted(tmp_path: Path):
    policy = PermissionPolicy(mode=PermissionMode.DEFAULT)
    tool = ConfigTool(policy, tmp_path)
    res = tool.run({"action": "allow", "pattern": "Bash(git *)"}, ToolContext(cwd=tmp_path))
    assert not res.is_error
    assert "Bash(git *)" in policy.allow                      # live
    assert "Bash(git *)" in _local(tmp_path)["allow"]         # persisted


def test_set_mode_live_and_persisted(tmp_path: Path):
    policy = PermissionPolicy(mode=PermissionMode.DEFAULT)
    tool = ConfigTool(policy, tmp_path)
    tool.run({"action": "set_mode", "value": "bypass"}, ToolContext(cwd=tmp_path))
    assert policy.mode == PermissionMode.BYPASS                # live
    assert _local(tmp_path)["permission_mode"] == "bypass"    # persisted


def test_set_model_updates_live_agent(tmp_path: Path):
    class FakeAgent:
        model = "deepseek-chat"
    agent = FakeAgent()
    tool = ConfigTool(PermissionPolicy(), tmp_path, session={"agent": agent})
    tool.run({"action": "set_model", "value": "deepseek-reasoner"}, ToolContext(cwd=tmp_path))
    assert agent.model == "deepseek-reasoner"                 # live
    assert _local(tmp_path)["model"] == "deepseek-reasoner"   # persisted


def test_set_style_validates(tmp_path: Path):
    tool = ConfigTool(PermissionPolicy(), tmp_path)
    bad = tool.run({"action": "set_style", "value": "nope"}, ToolContext(cwd=tmp_path))
    assert bad.is_error
    ok = tool.run({"action": "set_style", "value": "concise"}, ToolContext(cwd=tmp_path))
    assert not ok.is_error and _local(tmp_path)["output_style"] == "concise"


def test_invalid_mode_rejected(tmp_path: Path):
    tool = ConfigTool(PermissionPolicy(), tmp_path)
    res = tool.run({"action": "set_mode", "value": "yolo"}, ToolContext(cwd=tmp_path))
    assert res.is_error


def test_show_reports_state(tmp_path: Path):
    policy = PermissionPolicy(mode=PermissionMode.PLAN)
    res = ConfigTool(policy, tmp_path).run({"action": "show"}, ToolContext(cwd=tmp_path))
    assert "plan" in res.content
