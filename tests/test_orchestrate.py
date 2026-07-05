"""Orchestration primitives + deep-research harness (injected fakes, no network)."""
import threading
import time

from clims_core.orchestrate import parallel, pipeline, spawn_agent
from clims_core.research import deep_research
from clims_core.agent.message import Message
from clims_core.providers.base import StreamEvent
from tests.fake_provider import FakeProvider


def test_parallel_preserves_order_and_runs_concurrently():
    def make(i):
        def f():
            time.sleep(0.05)
            return i * 10
        return f
    results = parallel([make(i) for i in range(5)])
    assert results == [0, 10, 20, 30, 40]


def test_parallel_is_actually_concurrent():
    # 8 tasks each sleeping 0.1s should finish in well under 8*0.1 if parallel
    start = time.time()
    parallel([(lambda: time.sleep(0.1)) for _ in range(8)], max_workers=8)
    assert time.time() - start < 0.5


def test_parallel_error_becomes_none():
    def boom():
        raise ValueError("x")
    assert parallel([lambda: 1, boom, lambda: 3]) == [1, None, 3]


def test_pipeline_runs_stages_per_item():
    out = pipeline([1, 2, 3], lambda x: x + 1, lambda x: x * 10)
    assert sorted(out) == [20, 30, 40]


def test_spawn_agent_runs_child():
    provider = FakeProvider([[StreamEvent.text_delta("child answer"),
                              StreamEvent.finished("end_turn")]])
    out = spawn_agent(provider=provider, model="fake", api_key="k", task="do it")
    assert out == "child answer"
    assert any("do it" in m.text() for m in provider.calls[0])


# ---- deep-research harness with injected fakes ----

def test_deep_research_end_to_end():
    log = []

    def search_fn(query):
        return [{"url": f"https://ex.com/{query[:3]}", "title": "t", "snippet": "s"}]

    def fetch_fn(url):
        return f"page content for {url} with the fact: the sky is blue."

    def llm_fn(prompt):
        if "search queries" in prompt:
            return "what color is sky\nwhy sky blue\nsky physics"
        if "extract" in prompt.lower():
            return "- the sky is blue"
        if "fact-checker" in prompt.lower():
            return "No major issues found."
        # synthesize
        return "The sky is blue [1]. Sources: [1] ex.com"

    result = deep_research("why is the sky blue?", search_fn=search_fn, fetch_fn=fetch_fn,
                           llm_fn=llm_fn, max_queries=3, max_sources=4,
                           on_log=lambda m: log.append(m))
    assert result["queries"] and len(result["queries"]) <= 3
    assert result["sources"]  # urls collected
    assert "sky is blue" in result["report"].lower()
    assert "No major issues" in result["verification"]
    assert any("synthesizing" in m for m in log)


def test_deep_research_handles_no_sources():
    result = deep_research("q", search_fn=lambda q: [], fetch_fn=lambda u: "",
                           llm_fn=lambda p: "query1\nquery2", verify=False)
    assert result["sources"] == []
    assert "No usable sources" in result["report"]
