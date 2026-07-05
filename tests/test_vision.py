"""Vision sidecar: config resolution, vision.analyze, analyze_image tool."""
import base64
from pathlib import Path

import clims_core.vision as vision
from clims_core.config import load_config
from clims_core.providers.base import StreamEvent
from clims_core.tools.analyze_image import AnalyzeImageTool
from clims_core.tools.base import ToolContext

from tests.fake_provider import FakeProvider

PNG = b"\x89PNG\r\n\x1a\nFAKE"


def test_config_resolves_vision_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CLIMS_VISION_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "vkey")
    monkeypatch.delenv("CLIMS_VISION_MODEL", raising=False)
    cfg = load_config(tmp_path)
    assert cfg.vision_provider == "gemini"
    assert cfg.vision_model == "gemini-2.5-flash"  # default for gemini
    assert cfg.vision_api_key == "vkey"


def test_vision_analyze_returns_text(monkeypatch):
    fake = FakeProvider([[StreamEvent.text_delta("a red square"), StreamEvent.finished("end_turn")]])
    monkeypatch.setattr(vision, "get_provider", lambda name: fake)
    out = vision.analyze("gemini", "gemini-2.0-flash", "k",
                         [("image/png", base64.b64encode(PNG).decode())], "what is this?")
    assert out == "a red square"
    # the image + question were sent in a single user message
    sent = fake.calls[0][0]
    kinds = [type(b).__name__ for b in sent.content]
    assert "ImageBlock" in kinds and "TextBlock" in kinds


def test_analyze_image_tool_not_configured():
    t = AnalyzeImageTool("", "", "")
    r = t.run({"question": "what?", "path": "x.png"}, ToolContext())
    assert r.is_error and "no vision provider configured" in r.content


def test_analyze_image_tool_reads_local_and_calls(monkeypatch, tmp_path: Path):
    (tmp_path / "pic.png").write_bytes(PNG)
    monkeypatch.setattr(vision, "analyze",
                        lambda *a, **k: "two cats on a sofa")
    t = AnalyzeImageTool("gemini", "gemini-2.0-flash", "k")
    r = t.run({"question": "what's in it?", "path": "pic.png"}, ToolContext(cwd=tmp_path))
    assert not r.is_error and "two cats" in r.content


def test_analyze_image_missing_file(monkeypatch, tmp_path):
    t = AnalyzeImageTool("gemini", "gemini-2.0-flash", "k")
    r = t.run({"question": "?", "path": "nope.png"}, ToolContext(cwd=tmp_path))
    assert r.is_error and "not found" in r.content
