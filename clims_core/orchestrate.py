"""Multi-agent orchestration primitives.

The piece clims_code was missing: run many subagents/tasks CONCURRENTLY instead of
one-at-a-time. Model calls are I/O-bound (HTTP), so threads give real parallelism.
Providers are stateless per-call, so concurrent `chat()` is safe.

Primitives:
  - parallel(thunks)      : run callables concurrently, results in order (errors -> None)
  - pipeline(items, *fns) : run each item through all stages, concurrently across items
  - spawn_agent(...)      : build + run a child agent, return its final text

These are the building blocks for workflows (parallel review, fan-out research,
adversarial verification, loop-until-dry, etc.).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

DEFAULT_MAX_WORKERS = 8


def parallel(thunks: list[Callable], max_workers: int = DEFAULT_MAX_WORKERS) -> list:
    """Run zero-arg callables concurrently. Returns results in the SAME order as
    `thunks`. A thunk that raises yields None in its slot (never crashes the batch)."""
    n = len(thunks)
    if n == 0:
        return []
    results: list = [None] * n
    workers = min(max_workers, n)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut_to_i = {ex.submit(t): i for i, t in enumerate(thunks)}
        for fut in as_completed(fut_to_i):
            i = fut_to_i[fut]
            try:
                results[i] = fut.result()
            except Exception:
                results[i] = None
    return results


def pipeline(items: list, *stages: Callable, max_workers: int = DEFAULT_MAX_WORKERS) -> list:
    """Run each item through all stages independently and concurrently across items.
    No barrier between stages — item A can be in stage 3 while item B is in stage 1.
    A stage that raises drops that item to None."""
    def run_one(item):
        cur = item
        for stage in stages:
            cur = stage(cur)
        return cur
    return parallel([(lambda it=it: run_one(it)) for it in items], max_workers)


_VERIFY_LENSES = ["factual accuracy", "logical consistency", "completeness",
                  "possible counterexamples", "source reliability"]


def verify_claim(claim: str, llm_fn: Callable[[str], str], n: int = 3) -> dict:
    """Adversarial verification: spawn n skeptics (each with a DIFFERENT lens, so
    they don't just agree) to judge a claim, in parallel. Majority decides. Returns
    {claim, supported: bool, support_count, n, votes}."""
    n = max(1, n)
    lenses = (_VERIFY_LENSES * ((n // len(_VERIFY_LENSES)) + 1))[:n]

    def make(lens):
        prompt = (
            f"You are a skeptic focused on {lens}. Critically assess whether the claim "
            f"below is TRUE. Default to skepticism if uncertain. Respond with exactly "
            f"'SUPPORTED' or 'REFUTED' on the first line, then one short reason.\n\n"
            f"Claim: {claim}"
        )
        return lambda: llm_fn(prompt)

    votes = parallel([make(l) for l in lenses], max_workers=n)
    support = sum(1 for v in votes
                  if v and "SUPPORTED" in (v.split("\n", 1)[0].upper()))
    return {"claim": claim, "supported": support > n // 2,
            "support_count": support, "n": n, "votes": votes}


def spawn_agent(
    *,
    provider,
    model: str,
    api_key: str,
    task: str,
    system: str | None = None,
    tools: list | None = None,
    temperature: float | None = 0,
    max_iterations: int = 12,
    cwd=None,
    agent_type: str | None = None,
) -> str:
    """Build and run a focused child agent; return its final answer text. Designed to
    be called from many threads at once (each gets its own runtime/context). If
    `agent_type` names a specialist (explore/plan/reviewer/researcher), its tuned
    system prompt + tool allowlist + iteration budget are applied."""
    from clims_core.agent.loop import Agent
    from clims_core.agent.message import Message
    from clims_core.agent.runtime import ToolRuntime
    from clims_core.agent_types import get_agent_spec, filter_tools
    from clims_core.permissions.policy import PermissionMode, PermissionPolicy
    from clims_core.tools import default_tools, tool_map
    from clims_core.tools.base import ToolContext

    tool_list = tools if tools is not None else default_tools()
    spec = get_agent_spec(agent_type)
    if spec is not None:
        if system is None:
            system = spec.system
        tool_list = filter_tools(tool_list, spec.tools)
        max_iterations = spec.max_iterations

    ctx = ToolContext(cwd=cwd) if cwd is not None else ToolContext()
    runtime = ToolRuntime(tool_map(tool_list), PermissionPolicy(mode=PermissionMode.BYPASS), ctx)
    agent = Agent(provider=provider, model=model, api_key=api_key, runtime=runtime,
                  system=system, temperature=temperature, max_iterations=max_iterations,
                  auto_compact=False)
    result = agent.send([Message.user(task)], lambda e: None)
    return result.messages[-1].text() if result.messages else ""
