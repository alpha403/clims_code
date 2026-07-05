"""Workflow runner — deterministic multi-agent orchestration scripts.

A workflow is a Python file in `.clims/workflows/<name>.py` that defines
`def run(api): ...`. The `api` exposes the orchestration primitives so the script
can fan out agents, run pipelines, research, and synthesize — deterministically.

    # .clims/workflows/review.py
    def run(api):
        files = api.agent("List the changed files, one per line").splitlines()
        reviews = api.parallel([lambda f=f: api.agent(f"Review {f}", agent_type="reviewer")
                                for f in files])
        return "\n\n".join(r for r in reviews if r)

Security note: workflows are arbitrary Python from the project (like a Makefile);
only run workflows you trust. Self-hosted, single-tenant assumption.
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from clims_core.orchestrate import parallel, pipeline, spawn_agent

WORKFLOW_DIR = ".clims/workflows"


@dataclass
class WorkflowAPI:
    provider: object
    model: str
    api_key: str
    cwd: Path | None = None
    on_log: Callable[[str], None] | None = None

    # orchestration primitives
    def parallel(self, thunks, max_workers: int = 8):
        return parallel(thunks, max_workers)

    def pipeline(self, items, *stages, max_workers: int = 8):
        return pipeline(items, *stages, max_workers=max_workers)

    def agent(self, task: str, *, agent_type: str | None = None,
              system: str | None = None, tools=None, max_iterations: int = 12) -> str:
        return spawn_agent(provider=self.provider, model=self.model, api_key=self.api_key,
                           task=task, agent_type=agent_type, system=system, tools=tools,
                           max_iterations=max_iterations, cwd=self.cwd)

    def research(self, question: str) -> dict:
        from clims_core.research import deep_research
        from clims_core.tools.web_search import search_web
        from clims_core.tools.web_fetch import fetch_url_text

        def llm_fn(prompt: str) -> str:
            return spawn_agent(provider=self.provider, model=self.model, api_key=self.api_key,
                               task=prompt, tools=[], max_iterations=1)
        return deep_research(question, search_fn=search_web, fetch_fn=fetch_url_text,
                             llm_fn=llm_fn, on_log=self.log)

    def log(self, msg: str):
        if self.on_log:
            self.on_log(msg)


def _dirs(cwd: Path, home: Path) -> list[Path]:
    return [home / ".clims" / "workflows", cwd / ".clims" / "workflows"]


def list_workflows(cwd: Path | None = None, home: Path | None = None) -> list[str]:
    cwd = cwd or Path.cwd(); home = home or Path.home()
    names = []
    for d in _dirs(cwd, home):
        if d.is_dir():
            names += [f.stem for f in d.glob("*.py") if not f.stem.startswith("_")]
    return sorted(set(names))


def _find_workflow_file(name: str, cwd: Path, home: Path) -> Path | None:
    for d in _dirs(cwd, home):
        f = d / f"{name}.py"
        if f.is_file():
            return f
    return None


def run_workflow(name: str, api: WorkflowAPI, cwd: Path | None = None,
                 home: Path | None = None):
    cwd = cwd or Path.cwd(); home = home or Path.home()
    path = _find_workflow_file(name, cwd, home)
    if path is None:
        raise FileNotFoundError(f"workflow not found: {name} (in {WORKFLOW_DIR}/)")
    spec = importlib.util.spec_from_file_location(f"clims_workflow_{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load workflow {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "run"):
        raise AttributeError(f"workflow {name} must define run(api)")
    return module.run(api)
