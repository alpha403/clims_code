"""Background tasks, scheduler, agent types, workflow runner."""
from pathlib import Path

from clims_core.agent_types import get_agent_spec, filter_tools, agent_type_names
from clims_core.background import BackgroundTasks
from clims_core.orchestrate import spawn_agent
from clims_core.providers.base import StreamEvent
from clims_core.scheduler import Scheduler, SchedulerLoop
from clims_core.tools import default_tools
from clims_core.workflows import WorkflowAPI, run_workflow, list_workflows

from tests.fake_provider import FakeProvider


# ---- background ----
def test_background_task_completes():
    bt = BackgroundTasks()
    tid = bt.start(lambda: "result-x", label="job")
    task = bt.wait(tid, timeout=2)
    assert task.status == "done" and task.result == "result-x"


def test_background_task_error_isolated():
    bt = BackgroundTasks()
    def boom():
        raise ValueError("nope")
    tid = bt.start(boom)
    task = bt.wait(tid, timeout=2)
    assert task.status == "error" and "nope" in task.error


def test_background_on_complete_callback():
    seen = {}
    bt = BackgroundTasks(on_complete=lambda t: seen.update(id=t.id))
    tid = bt.start(lambda: "ok")
    bt.wait(tid, timeout=2)
    assert seen.get("id") == tid


# ---- scheduler ----
def test_scheduler_due_and_mark(tmp_path: Path):
    s = Scheduler(path=tmp_path / "sch.json")
    sid = s.add("run me", interval_seconds=60, label="job")
    assert s.due(now=0) == []           # not due at t=0 (last_run defaults 0, interval 60)
    due = s.due(now=60)
    assert len(due) == 1 and due[0].id == sid
    s.mark_run(sid, now=60)
    assert s.due(now=90) == []          # ran at 60, not due again until 120
    assert s.due(now=120)               # due again


def test_scheduler_persists(tmp_path: Path):
    p = tmp_path / "sch.json"
    s1 = Scheduler(path=p)
    sid = s1.add("task", 30)
    s2 = Scheduler(path=p)              # reload
    assert any(x.id == sid for x in s2.list())


def test_scheduler_loop_runs_due():
    s = Scheduler(path=Path("nonexistent_dir_xyz") / "x.json")
    s.add("hello", interval_seconds=10)
    ran = []
    loop = SchedulerLoop(s, runner=lambda p: ran.append(p), clock=lambda: 999)
    loop.run_once()
    assert ran == ["hello"]


# ---- agent types ----
def test_agent_types_registry():
    assert set(agent_type_names()) >= {"explore", "plan", "reviewer", "researcher"}
    explore = get_agent_spec("explore")
    assert explore and "read-only" in explore.system.lower()
    assert "write" not in (explore.tools or [])     # read-only specialist can't write


def test_filter_tools():
    tools = default_tools()
    filtered = filter_tools(tools, ["read", "grep"])
    names = {t.name for t in filtered}
    assert names == {"read", "grep"}


def test_spawn_agent_with_type_applies_spec():
    provider = FakeProvider([[StreamEvent.text_delta("explored"), StreamEvent.finished("end_turn")]])
    out = spawn_agent(provider=provider, model="fake", api_key="k",
                      task="look around", agent_type="explore")
    assert out == "explored"


# ---- workflows ----
def _write_wf(tmp_path: Path, name: str, body: str):
    d = tmp_path / ".clims" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.py").write_text(body, encoding="utf-8")


def test_list_and_run_workflow(tmp_path: Path):
    _write_wf(tmp_path, "sample",
              "def run(api):\n    return api.parallel([lambda: 1, lambda: 2, lambda: 3])\n")
    home = tmp_path / "home"; home.mkdir()
    assert "sample" in list_workflows(cwd=tmp_path, home=home)
    api = WorkflowAPI(provider=FakeProvider([]), model="fake", api_key="k", cwd=tmp_path)
    result = run_workflow("sample", api, cwd=tmp_path, home=home)
    assert result == [1, 2, 3]


def test_workflow_uses_agents(tmp_path: Path):
    _write_wf(tmp_path, "agents",
              "def run(api):\n"
              "    return api.parallel([lambda: api.agent('q1'), lambda: api.agent('q2')])\n")
    home = tmp_path / "home"; home.mkdir()
    provider = FakeProvider([
        [StreamEvent.text_delta("a1"), StreamEvent.finished("end_turn")],
        [StreamEvent.text_delta("a2"), StreamEvent.finished("end_turn")],
    ])
    api = WorkflowAPI(provider=provider, model="fake", api_key="k", cwd=tmp_path)
    result = run_workflow("agents", api, cwd=tmp_path, home=home)
    assert sorted(result) == ["a1", "a2"]


def test_run_unknown_workflow_raises(tmp_path: Path):
    home = tmp_path / "home"; home.mkdir()
    api = WorkflowAPI(provider=FakeProvider([]), model="fake", api_key="k")
    try:
        run_workflow("nope", api, cwd=tmp_path, home=home)
        assert False
    except FileNotFoundError:
        pass
