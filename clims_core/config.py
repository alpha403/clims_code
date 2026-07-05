"""Configuration loader.

Settings hierarchy (low → high precedence), each an optional JSON file:
    user      ~/.clims/settings.json
    project   ./.clims/settings.json
    local     ./.clims/settings.local.json   (gitignored)
Then environment variables override file values for the hot fields.

BYOK: api keys may come from env (CLIMS_API_KEY / provider-specific) but are
never written back to any settings file.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Config:
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    api_key: str = ""
    permission_mode: str = "default"
    temperature: float | None = None
    max_tokens: int | None = None
    allow: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)
    ask: list[str] = field(default_factory=list)
    system: str | None = None
    output_style: str | None = None
    proactive_memory: bool = True
    mcp_servers: dict = field(default_factory=dict)
    hooks: dict = field(default_factory=dict)
    # optional vision sidecar: a separate vision-capable provider used by the
    # analyze_image tool when the main (text) model can't see. BYOK, never persisted.
    vision_provider: str = ""
    vision_model: str = ""
    vision_api_key: str = ""

    def redacted_vision(self) -> str:
        return f"{self.vision_provider}:{self.vision_model}" if self.vision_provider else ""

    def redacted(self) -> dict:
        d = asdict(self)
        d["api_key"] = "***" if self.api_key else ""
        return d


_ENV_KEYS = {
    "deepseek": ["DEEPSEEK_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY", "CLAUDE_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
}

# sensible default vision model per provider (used if only a vision provider is given)
_VISION_DEFAULT_MODEL = {
    "gemini": "gemini-2.5-flash",   # current flagship flash; vision-capable; free-tier eligible
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-6",
    "ollama": "llama3.2-vision",
}


def _resolve_vision(cfg: "Config", merged: dict) -> None:
    vision = merged.get("vision", {}) or {}
    cfg.vision_provider = os.environ.get("CLIMS_VISION_PROVIDER", vision.get("provider", "")) or ""
    cfg.vision_model = (os.environ.get("CLIMS_VISION_MODEL")
                        or vision.get("model")
                        or _VISION_DEFAULT_MODEL.get(cfg.vision_provider, ""))
    cfg.vision_api_key = os.environ.get("CLIMS_VISION_API_KEY", "")
    if not cfg.vision_api_key and cfg.vision_provider:
        for env_name in _ENV_KEYS.get(cfg.vision_provider, []):
            if os.environ.get(env_name):
                cfg.vision_api_key = os.environ[env_name]
                break


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_config(cwd: Path | None = None) -> Config:
    cwd = cwd or Path.cwd()
    layers = [
        Path.home() / ".clims" / "settings.json",
        cwd / ".clims" / "settings.json",
        cwd / ".clims" / "settings.local.json",
    ]
    merged: dict = {}
    for p in layers:
        merged.update(_load_json(p))

    cfg = Config(
        provider=merged.get("provider", "deepseek"),
        model=merged.get("model", "deepseek-chat"),
        permission_mode=merged.get("permission_mode", "default"),
        temperature=merged.get("temperature"),
        max_tokens=merged.get("max_tokens"),
        allow=list(merged.get("allow", [])),
        deny=list(merged.get("deny", [])),
        ask=list(merged.get("ask", [])),
        system=merged.get("system"),
        output_style=merged.get("output_style"),
        proactive_memory=merged.get("proactive_memory", True),
        mcp_servers=dict(merged.get("mcpServers", {})),
        hooks=dict(merged.get("hooks", {})),
    )

    # also accept a standalone .clims/mcp.json (mcpServers key or bare map)
    mcp_json = _load_json(cwd / ".clims" / "mcp.json")
    if mcp_json:
        cfg.mcp_servers.update(mcp_json.get("mcpServers", mcp_json))

    # env overrides for hot fields
    cfg.provider = os.environ.get("CLIMS_PROVIDER", cfg.provider)
    cfg.model = os.environ.get("CLIMS_MODEL", cfg.model)
    cfg.permission_mode = os.environ.get("CLIMS_PERMISSION_MODE", cfg.permission_mode)
    if os.environ.get("CLIMS_NO_PROACTIVE_MEMORY") == "1":
        cfg.proactive_memory = False

    # BYOK key resolution: explicit generic env, then provider-specific env
    cfg.api_key = os.environ.get("CLIMS_API_KEY", "")
    if not cfg.api_key:
        for env_name in _ENV_KEYS.get(cfg.provider, []):
            if os.environ.get(env_name):
                cfg.api_key = os.environ[env_name]
                break

    _resolve_vision(cfg, merged)
    return cfg
