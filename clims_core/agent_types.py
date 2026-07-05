"""Specialized agent types — curated, tuned sub-agent presets.

Each type has its own system prompt, an optional tool allowlist (e.g. read-only
explorers can't write), and an iteration budget. Used by spawn_agent / the
subagent tool via `agent_type=...`. Complements file-defined agents (.clims/agents).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentSpec:
    name: str
    system: str
    tools: list[str] | None = None   # allowlist of tool names; None = all defaults
    max_iterations: int = 12


_READONLY = ["read", "glob", "grep", "web_fetch", "web_search", "todo"]

AGENT_TYPES: dict[str, AgentSpec] = {
    "explore": AgentSpec(
        "explore",
        "You are a read-only exploration agent. Search and read to answer the question "
        "thoroughly; do NOT modify anything. Report concise findings with file_path:line "
        "references and a short summary.",
        tools=_READONLY, max_iterations=18,
    ),
    "plan": AgentSpec(
        "plan",
        "You are a planning agent. Research read-only, then produce a concrete, ordered "
        "step-by-step plan to accomplish the goal. Do NOT modify files. Output only the plan.",
        tools=["read", "glob", "grep"], max_iterations=14,
    ),
    "reviewer": AgentSpec(
        "reviewer",
        "You are a meticulous code reviewer. Review for correctness bugs, security issues, "
        "and clear style problems. Cite file_path:line for each finding. Do NOT modify files.",
        tools=["read", "glob", "grep"], max_iterations=14,
    ),
    "researcher": AgentSpec(
        "researcher",
        "You are a web research agent. Use web_search and web_fetch to gather information "
        "from multiple sources, then synthesize a concise, cited answer. Do NOT modify files.",
        tools=["web_search", "web_fetch", "read"], max_iterations=20,
    ),
}


def get_agent_spec(name: str | None) -> AgentSpec | None:
    if not name:
        return None
    return AGENT_TYPES.get(name.lower())


def filter_tools(tools: list, allowed: list[str] | None) -> list:
    if not allowed:
        return tools
    allow = set(allowed)
    return [t for t in tools if getattr(t, "name", None) in allow]


def agent_type_names() -> list[str]:
    return sorted(AGENT_TYPES)
