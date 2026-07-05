"""Custom command + file-defined agent loader tests."""
from pathlib import Path

from clims_core.commands import load_commands, expand_command, load_agents


def _mk(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_load_and_expand_commands(tmp_path: Path):
    _mk(tmp_path / ".clims" / "commands" / "review.md",
        "Review this code for bugs:\n$ARGUMENTS")
    home = tmp_path / "home"; home.mkdir()
    cmds = load_commands(cwd=tmp_path, home=home)
    assert "review" in cmds
    expanded = expand_command(cmds["review"], "foo.py")
    assert "Review this code" in expanded and "foo.py" in expanded


def test_expand_without_placeholder_appends():
    out = expand_command("Summarize the repo.", "extra context")
    assert "Summarize the repo." in out and "extra context" in out


def test_load_agents_with_frontmatter(tmp_path: Path):
    _mk(tmp_path / ".clims" / "agents" / "researcher.md",
        "---\n"
        "name: researcher\n"
        "description: deep web research\n"
        "model: deepseek-chat\n"
        "tools: web_search, web_fetch, read\n"
        "---\n"
        "You are a meticulous research agent. Cite sources.")
    home = tmp_path / "home"; home.mkdir()
    agents = load_agents(cwd=tmp_path, home=home)
    assert "researcher" in agents
    a = agents["researcher"]
    assert a.description == "deep web research"
    assert a.model == "deepseek-chat"
    assert a.tools == ["web_search", "web_fetch", "read"]
    assert "meticulous research agent" in a.system


def test_agent_without_frontmatter(tmp_path: Path):
    _mk(tmp_path / ".clims" / "agents" / "plain.md", "Just a system prompt body.")
    home = tmp_path / "home"; home.mkdir()
    agents = load_agents(cwd=tmp_path, home=home)
    assert agents["plain"].system == "Just a system prompt body."


def test_no_dirs_returns_empty(tmp_path: Path):
    home = tmp_path / "home"; home.mkdir()
    assert load_commands(cwd=tmp_path, home=home) == {}
    assert load_agents(cwd=tmp_path, home=home) == {}
