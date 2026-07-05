"""Proactive memory & self-documentation: digest + system assembly."""
from pathlib import Path

from clims_core.agent.loop import assemble_system, MEMORY_BEHAVIOR
from clims_core.memory import memory_digest


def test_memory_digest_reads_memory_and_tracking_docs(tmp_path: Path):
    md = tmp_path / ".clims" / "memory"
    md.mkdir(parents=True)
    (md / "facts.md").write_text("User prefers tabs.", encoding="utf-8")
    (tmp_path / "PROGRESS.md").write_text("Phase 2 in progress.", encoding="utf-8")
    digest = memory_digest(tmp_path)
    assert "User prefers tabs." in digest
    assert "memory/facts.md" in digest
    assert "PROGRESS.md" in digest and "Phase 2 in progress." in digest


def test_memory_digest_empty(tmp_path: Path):
    assert memory_digest(tmp_path) == ""


def test_assemble_system_includes_behavior_and_digest():
    s = assemble_system("BASE", memory="proj rules", digest="known fact", proactive=True)
    assert "BASE" in s
    assert "Proactive memory" in s  # behavior block present
    assert "proj rules" in s
    assert "known fact" in s


def test_assemble_system_proactive_off_omits_behavior():
    s = assemble_system("BASE", memory="proj rules", digest="known fact", proactive=False)
    assert "BASE" in s and "proj rules" in s
    assert "Proactive memory" not in s  # behavior suppressed
    assert "known fact" not in s  # digest not injected when off


def test_behavior_mentions_the_docs():
    for token in ("memory` tool", "PROGRESS.md", "DECISIONS.md", "ARCHITECTURE.md",
                  "never store secrets"):
        assert token in MEMORY_BEHAVIOR
