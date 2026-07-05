"""Custom slash commands and file-defined subagents.

Custom commands:  .clims/commands/<name>.md  (and ~/.clims/commands/)
    The file body is a prompt template. `$ARGUMENTS` is replaced with whatever
    the user typed after `/<name>`. Invoking `/name foo bar` sends the expanded
    template as the user's message.

File-defined agents:  .clims/agents/<name>.md  (and ~/.clims/agents/)
    Optional `---` frontmatter (name/description/model/tools) followed by the
    agent's system prompt body. Used as named subagents.

Frontmatter is parsed without a YAML dependency (simple `key: value` lines).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


def _command_dirs(cwd: Path, home: Path) -> list[Path]:
    return [home / ".clims" / "commands", cwd / ".clims" / "commands"]


def _agent_dirs(cwd: Path, home: Path) -> list[Path]:
    return [home / ".clims" / "agents", cwd / ".clims" / "agents"]


def load_commands(cwd: Path | None = None, home: Path | None = None) -> dict:
    cwd = (cwd or Path.cwd()); home = home or Path.home()
    out: dict[str, str] = {}
    for d in _command_dirs(cwd, home):
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            try:
                out[f.stem] = f.read_text(encoding="utf-8")
            except OSError:
                continue
    return out


def expand_command(template: str, args: str) -> str:
    if "$ARGUMENTS" in template:
        return template.replace("$ARGUMENTS", args)
    return template if not args else f"{template}\n\n{args}"


@dataclass
class AgentDef:
    name: str
    description: str = ""
    model: str | None = None
    tools: list[str] = field(default_factory=list)
    system: str = ""


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    meta = {}
    for line in lines[1:end]:
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    body = "\n".join(lines[end + 1:]).strip()
    return meta, body


@dataclass
class SkillDef:
    name: str
    description: str = ""
    body: str = ""


def _bundled_skills_dir() -> Path:
    """Default skills shipped inside the installed package (lowest priority)."""
    return Path(__file__).resolve().parent / "data" / "skills"


def load_skills(cwd: Path | None = None, home: Path | None = None) -> dict:
    """Load skills from .clims/skills/<name>.md or .clims/skills/<name>/SKILL.md.

    Priority (lowest → highest, later values win):
      1. Package built-in skills  (clims_core/data/skills/)
      2. ~/.clims/skills/         (user global)
      3. cwd/.clims/skills/       (project-local, highest priority)
    """
    cwd = (cwd or Path.cwd()); home = home or Path.home()
    out: dict[str, SkillDef] = {}
    for base in (_bundled_skills_dir(), home / ".clims" / "skills", cwd / ".clims" / "skills"):
        if not base.is_dir():
            continue
        candidates = list(base.glob("*.md")) + list(base.glob("*/SKILL.md"))
        for f in sorted(candidates):
            try:
                text = f.read_text(encoding="utf-8")
            except OSError:
                continue
            meta, body = _parse_frontmatter(text)
            name = meta.get("name") or (f.parent.name if f.name == "SKILL.md" else f.stem)
            out[name] = SkillDef(name=name, description=meta.get("description", ""), body=body)
    return out


def load_agents(cwd: Path | None = None, home: Path | None = None) -> dict:
    cwd = (cwd or Path.cwd()); home = home or Path.home()
    out: dict[str, AgentDef] = {}
    for d in _agent_dirs(cwd, home):
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            try:
                text = f.read_text(encoding="utf-8")
            except OSError:
                continue
            meta, body = _parse_frontmatter(text)
            name = meta.get("name", f.stem)
            tools = [t.strip() for t in meta.get("tools", "").split(",") if t.strip()]
            out[name] = AgentDef(
                name=name,
                description=meta.get("description", ""),
                model=meta.get("model") or None,
                tools=tools,
                system=body,
            )
    return out
