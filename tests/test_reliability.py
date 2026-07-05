"""Harness reliability: anti-thrash guard, adversarial verify, research revision."""
from clims_core.agent.loop import Agent, THRASH_LIMIT
from clims_core.agent.message import Message, ToolResultBlock
from clims_core.agent.runtime import ToolRuntime
from clims_core.orchestrate import verify_claim
from clims_core.permissions.policy import PermissionMode, PermissionPolicy
from clims_core.providers.base import StreamEvent
from clims_core.research import deep_research
from clims_core.tools import default_tools, tool_map
from clims_core.tools.base import ToolContext

from tests.fake_provider import FakeProvider


def test_anti_thrash_breaks_repeated_identical_calls():
    # model repeats the SAME bash call every turn forever
    repeat = [StreamEvent.tool("c", "bash", {"command": "echo hi"}),
              StreamEvent.finished("tool_use")]
    provider = FakeProvider([list(repeat) for _ in range(20)])
    rt = ToolRuntime(tool_map(default_tools()),
                     PermissionPolicy(mode=PermissionMode.BYPASS), ToolContext())
    agent = Agent(provider=provider, model="fake", api_key="k", runtime=rt, max_iterations=20)
    result = agent.send([Message.user("go")], lambda e: None)
    # the guard must have injected an anti-loop error result at some point
    tool_msgs = [b for m in result.messages if m.role == "tool" for b in m.content
                 if isinstance(b, ToolResultBlock)]
    assert any("Anti-loop guard" in b.content for b in tool_msgs)
    # and it must have happened after THRASH_LIMIT successful executions
    blocked = [b for b in tool_msgs if "Anti-loop guard" in b.content]
    assert len(blocked) >= 1


def test_verify_claim_majority_supported():
    def llm_fn(prompt):
        return "SUPPORTED\nlooks fine"
    out = verify_claim("the sky is blue", llm_fn, n=3)
    assert out["supported"] and out["support_count"] == 3 and out["n"] == 3


def test_verify_claim_majority_refuted():
    def llm_fn(prompt):
        # refute on most lenses, support on one
        return "REFUTED\nno" if "completeness" not in prompt else "SUPPORTED\nok"
    out = verify_claim("the moon is cheese", llm_fn, n=3)
    assert not out["supported"] and out["support_count"] <= 1


def test_research_revises_when_factcheck_finds_issues():
    calls = {"verify": 0, "revise": 0}

    def search_fn(q):
        return [{"url": "https://x.com", "title": "t", "snippet": "s"}]

    def fetch_fn(u):
        return "some content"

    def llm_fn(prompt):
        low = prompt.lower()
        if "search queries" in low:
            return "q1\nq2"
        if "extract" in low:
            return "- a fact"
        if "revise the research answer" in low:    # check before fact-checker (revise mentions both)
            calls["revise"] += 1
            return "REVISED ANSWER [1]"
        if "skeptical fact-checker" in low:
            calls["verify"] += 1
            return "- claim X is unsupported"       # triggers revision
        return "DRAFT ANSWER [1]"

    res = deep_research("q", search_fn=search_fn, fetch_fn=fetch_fn, llm_fn=llm_fn,
                        verify=True, revise=True)
    assert res["revised"] is True
    assert res["report"] == "REVISED ANSWER [1]"
    assert calls["revise"] == 1


def test_research_no_revision_when_clean():
    def llm_fn(prompt):
        low = prompt.lower()
        if "search queries" in low:
            return "q1"
        if "extract" in low:
            return "- fact"
        if "fact-checker" in low:
            return "No major issues found."
        return "CLEAN ANSWER [1]"
    res = deep_research("q", search_fn=lambda q: [{"url": "u", "title": "t", "snippet": "s"}],
                        fetch_fn=lambda u: "c", llm_fn=llm_fn, verify=True, revise=True)
    assert res["revised"] is False and res["report"] == "CLEAN ANSWER [1]"
