"""Image-in-tool-result: Read returns an image; adapters wire it per dialect."""
import base64
from pathlib import Path

from clims_core.agent.message import Message, ToolResultBlock
from clims_core.providers.anthropic import AnthropicProvider
from clims_core.providers.deepseek import DeepSeekProvider
from clims_core.providers.gemini import GeminiProvider
from clims_core.tools import ReadTool
from clims_core.tools.base import ToolContext

FAKE_IMG = base64.b64encode(b"\x89PNG\r\n\x1a\nFAKEDATA").decode()


def _tool_msg():
    return Message(role="tool", content=[ToolResultBlock(
        tool_use_id="t1", content="[image: pic.png]",
        images=[{"media_type": "image/png", "data": FAKE_IMG}])])


def test_read_returns_image(tmp_path: Path):
    (tmp_path / "pic.png").write_bytes(b"\x89PNG\r\n\x1a\nHELLO")
    res = ReadTool().run({"path": "pic.png"}, ToolContext(cwd=tmp_path))
    assert res.images and res.images[0]["media_type"] == "image/png"
    assert base64.b64decode(res.images[0]["data"]).startswith(b"\x89PNG")


def test_anthropic_image_in_tool_result():
    msgs = AnthropicProvider()._messages_wire([_tool_msg()])
    block = msgs[0]["content"][0]
    assert block["type"] == "tool_result"
    # content is a list with a text + image block
    types = [c["type"] for c in block["content"]]
    assert "image" in types
    img = next(c for c in block["content"] if c["type"] == "image")
    assert img["source"]["media_type"] == "image/png" and img["source"]["data"] == FAKE_IMG


def test_openai_image_followup_user_message():
    msgs = DeepSeekProvider()._messages_wire([_tool_msg()], system=None)
    # a tool message, then a user message carrying the image_url
    assert msgs[0]["role"] == "tool"
    user = next(m for m in msgs if m["role"] == "user")
    img_part = next(p for p in user["content"] if p["type"] == "image_url")
    assert img_part["image_url"]["url"].startswith("data:image/png;base64,")


def test_gemini_image_inline_data():
    contents = GeminiProvider()._contents_wire([_tool_msg()])
    # functionResponse content, then a user content with inlineData
    has_inline = any("inlineData" in p
                     for c in contents for p in c.get("parts", []))
    assert has_inline
