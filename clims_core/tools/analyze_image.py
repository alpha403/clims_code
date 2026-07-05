"""analyze_image tool — let the agent SEE an image via the vision sidecar.

The main (text) model calls this to read/describe a screenshot, diagram, UI mockup,
photo, or to OCR an image. The image is sent to the configured vision provider and a
text answer is returned. Requires a vision provider to be configured (cfg.vision_*).
"""
from __future__ import annotations

import base64
import mimetypes
import ssl
import urllib.request

from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult

MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB cap


def _media_type(name: str) -> str:
    mt, _ = mimetypes.guess_type(name)
    return mt if (mt and mt.startswith("image/")) else "image/png"


class AnalyzeImageTool(Tool):
    name = "analyze_image"
    description = (
        "Look at an image and answer a question about it — read a screenshot, describe a "
        "photo, interpret a diagram/chart, OCR text, identify COLORS / brand palette / visual "
        "style, or analyze a UI/design/logo mockup. This is the PREFERRED way to understand "
        "what an image looks like — use it instead of writing image-processing code (PIL, etc.), "
        "which may not be installed. (Only write code for exact programmatic pixel/hex extraction "
        "when the user specifically asks for that.) Provide `path` (a local file) or `url`, plus "
        "the `question` you want answered."
    )
    permission = PermissionClass.NETWORK  # sends the image to an external vision API
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "local image file path"},
            "url": {"type": "string", "description": "image URL (alternative to path)"},
            "question": {"type": "string",
                         "description": "what to determine about the image"},
        },
        "required": ["question"],
    }

    def __init__(self, provider: str, model: str, api_key: str):
        self.provider = provider
        self.model = model
        self.api_key = api_key

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        if not (self.provider and self.model and self.api_key):
            return ToolResult.error(
                "analyze_image: no vision provider configured. Set one, e.g. "
                "CLIMS_VISION_PROVIDER=gemini + GEMINI_API_KEY (model defaults to "
                "gemini-2.0-flash), or a 'vision' block in .clims/settings.json.")
        question = input.get("question") or "Describe this image."
        path, url = input.get("path"), input.get("url")
        if not path and not url:
            return ToolResult.error("analyze_image: provide 'path' or 'url'")

        try:
            if path:
                target = ctx.resolve(path)
                if not target.is_file():
                    return ToolResult.error(f"analyze_image: file not found: {target}")
                raw = target.read_bytes()
                media = _media_type(target.name)
            else:
                raw, media = _fetch(url)
        except Exception as e:  # noqa: BLE001
            return ToolResult.error(f"analyze_image: could not load image: {e}")

        if len(raw) > MAX_IMAGE_BYTES:
            return ToolResult.error(
                f"analyze_image: image too large ({len(raw)} bytes > {MAX_IMAGE_BYTES}).")

        b64 = base64.b64encode(raw).decode("ascii")
        from clims_core import vision
        try:
            answer = vision.analyze(self.provider, self.model, self.api_key,
                                    [(media, b64)], question)
        except Exception as e:  # noqa: BLE001
            return ToolResult.error(f"analyze_image: vision provider error: {e}")
        return ToolResult.ok(answer or "(vision model returned no text)")


def _fetch(url: str) -> tuple[bytes, str]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "clims_code/0.1"})
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        raw = resp.read(MAX_IMAGE_BYTES + 1)
        ctype = resp.headers.get("Content-Type", "")
    media = ctype.split(";")[0].strip() if ctype.startswith("image/") else _media_type(url)
    return raw, media
