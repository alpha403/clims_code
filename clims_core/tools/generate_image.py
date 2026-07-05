"""generate_image tool — text-to-image via Google Imagen 3 OR local ComfyUI.

Provider selection (in order of preference):
  1. comfyui  — if COMFYUI_API_URL is set  (local RTX box, best quality, free)
  2. google   — if GOOGLE_API_KEY is set    (Imagen 3, cloud, fast)

Both return a saved PNG path; the agent then calls send_file_to_telegram to deliver it.
"""
from __future__ import annotations

import base64
import json
import os
import random
import time
import urllib.error
import urllib.request
from pathlib import Path

from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult

# ── aspect ratio helpers ───────────────────────────────────────────────────────

_RATIO_TO_WH = {
    "1:1":  (1024, 1024),
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "4:3":  (1024, 768),
    "3:4":  (768, 1024),
}


# ── Google image generation ────────────────────────────────────────────────────
# Tries providers in order until one works:
#   1. Imagen 3/4 via :predict  (requires Imagen allowlist on the key)
#   2. Gemini flash image generation via :generateContent  (any standard API key)

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Primary model — proven working ("nano banana" = gemini-2.5-flash-image)
# Fallbacks tried if the primary returns a 404/403 (model availability varies by key)
_GEMINI_IMG_MODELS = [
    "gemini-2.5-flash-image",
    "gemini-2.0-flash-preview-image-generation",
    "gemini-2.0-flash-exp",
]


def _post(url: str, body: bytes) -> dict:
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def _extract_images(data: dict) -> list[bytes]:
    images = []
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data") or {}
            if inline.get("data"):
                images.append(base64.b64decode(inline["data"]))
    return images


def _google_generate(prompt: str, aspect_ratio: str, count: int, api_key: str) -> list[bytes]:
    """
    Generate images via gemini-2.5-flash-image (nano banana) with fallbacks.
    Uses the exact request format proven in bench/_icon_only.py.
    """
    body_dict = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": aspect_ratio},
        },
    }
    body = json.dumps(body_dict).encode()

    last_error = None
    for model in _GEMINI_IMG_MODELS:
        url = f"{_BASE}/{model}:generateContent?key={api_key}"
        try:
            data = _post(url, body)
            images = _extract_images(data)
            if not images:
                continue
            # generateContent returns 1 image per call — loop for count > 1
            while len(images) < count:
                extra = _extract_images(_post(url, body))
                if not extra:
                    break
                images.extend(extra)
            return images[:count]
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            if exc.code in (400, 403, 404):
                last_error = f"{model} — HTTP {exc.code}: {detail[:120]}"
                continue
            raise RuntimeError(f"Gemini image API error {exc.code}: {detail}")
        except Exception as exc:
            last_error = str(exc)
            continue

    raise RuntimeError(
        f"Image generation failed. Last error: {last_error}\n"
        "Tip: set up ComfyUI for reliable local generation — run /setup and add your ComfyUI URL."
    )


# ── ComfyUI ────────────────────────────────────────────────────────────────────

def _comfy_url(base: str, path: str) -> str:
    return base.rstrip("/") + path


def _comfy_generate(
    prompt: str, width: int, height: int,
    count: int, api_url: str, model: str,
) -> list[bytes]:
    """POST a Flux text-to-image workflow to a ComfyUI instance and return PNG bytes."""

    workflow = {
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": model},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["4", 1], "text": prompt},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["4", 1], "text": ""},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": count},
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "model":        ["4", 0],
                "positive":     ["6", 0],
                "negative":     ["7", 0],
                "latent_image": ["5", 0],
                "seed":         random.randint(0, 2**32 - 1),
                "steps":        25,
                "cfg":          1.0,
                "sampler_name": "euler",
                "scheduler":    "simple",
                "denoise":      1.0,
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"images": ["8", 0], "filename_prefix": "clims_gen"},
        },
    }

    # POST the prompt
    body = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(
        _comfy_url(api_url, "/prompt"),
        data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_data = json.loads(resp.read())
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Cannot reach ComfyUI at {api_url}: {exc.reason}\n"
            "Check the URL is correct and the ComfyUI server is running."
        )

    prompt_id = resp_data.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI did not return a prompt_id: {resp_data}")

    # Poll history until done
    deadline = time.time() + 300  # 5-min timeout
    while time.time() < deadline:
        time.sleep(3)
        hist_req = urllib.request.Request(_comfy_url(api_url, f"/history/{prompt_id}"))
        try:
            with urllib.request.urlopen(hist_req, timeout=10) as hr:
                hist = json.loads(hr.read())
        except Exception:
            continue
        if prompt_id not in hist:
            continue
        outputs = hist[prompt_id].get("outputs", {})
        images: list[bytes] = []
        for node_out in outputs.values():
            for img in node_out.get("images", []):
                fname    = img["filename"]
                subfolder = img.get("subfolder", "")
                img_type  = img.get("type", "output")
                view_url  = (
                    _comfy_url(api_url, "/view")
                    + f"?filename={urllib.parse.quote(fname)}"
                    + f"&subfolder={urllib.parse.quote(subfolder)}"
                    + f"&type={img_type}"
                )
                with urllib.request.urlopen(view_url, timeout=60) as ir:
                    images.append(ir.read())
        if images:
            return images
    raise RuntimeError("ComfyUI timed out after 5 minutes.")


# ── tool ───────────────────────────────────────────────────────────────────────

class GenerateImageTool(Tool):
    name = "generate_image"
    description = (
        "Generate an image from a text prompt using AI. "
        "Automatically uses ComfyUI (local RTX box) if configured, "
        "otherwise falls back to Google Imagen 3. "
        "After generating, call send_file_to_telegram to send the image to the user. "
        "If neither COMFYUI_API_URL nor GOOGLE_API_KEY is set, ask the user to run /setup."
    )
    permission = PermissionClass.MUTATING
    input_schema = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Detailed image description. Include style, mood, composition, colors.",
            },
            "output_path": {
                "type": "string",
                "description": "Where to save the PNG. Defaults to a timestamped file in cwd.",
            },
            "aspect_ratio": {
                "type": "string",
                "description": "1:1 (square), 16:9 (landscape), 9:16 (portrait/story), 4:3, 3:4. Default: 1:1",
                "enum": ["1:1", "16:9", "9:16", "4:3", "3:4"],
            },
            "count": {
                "type": "integer",
                "description": "Number of images to generate (1-4). Default: 1",
                "minimum": 1,
                "maximum": 4,
            },
            "provider": {
                "type": "string",
                "description": "Force a specific provider: 'auto' (default), 'comfyui', or 'google'.",
                "enum": ["auto", "comfyui", "google"],
            },
        },
        "required": ["prompt"],
    }

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:  # noqa: A002
        import urllib.parse  # noqa: PLC0415 — needed inside _comfy_generate closure

        prompt       = input["prompt"]
        output_path  = input.get("output_path")
        aspect_ratio = input.get("aspect_ratio", "1:1")
        count        = min(max(int(input.get("count", 1)), 1), 4)
        provider     = input.get("provider", "auto")

        comfy_url    = os.environ.get("COMFYUI_API_URL", "").strip()
        comfy_model  = os.environ.get("COMFYUI_MODEL", "flux1-dev.safetensors").strip()
        google_key   = (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")).strip()

        # Provider selection
        use_comfy  = (provider == "comfyui") or (provider == "auto" and bool(comfy_url))
        use_google = (provider == "google")  or (provider == "auto" and not use_comfy and bool(google_key))

        if not use_comfy and not use_google:
            return ToolResult.error(
                "No image generation provider configured.\n"
                "• For ComfyUI (local): run /setup and provide your ComfyUI API URL "
                "(e.g. http://100.84.108.103:8188)\n"
                "• For Google Imagen: run /setup and add your Google API key."
            )

        width, height = _RATIO_TO_WH.get(aspect_ratio, (1024, 1024))

        try:
            if use_comfy:
                if not comfy_url:
                    return ToolResult.error(
                        "ComfyUI selected but COMFYUI_API_URL is not set. "
                        "Run /setup to configure it."
                    )
                # import here so the module-level import stays clean
                import urllib.parse as _up  # noqa: PLC0415
                globals()["urllib"] = __import__("urllib")
                globals()["urllib"].parse = _up
                raw_images = _comfy_generate(prompt, width, height, count, comfy_url, comfy_model)
                provider_label = f"ComfyUI ({comfy_url}) model={comfy_model}"
            else:
                raw_images = _google_generate(prompt, aspect_ratio, count, google_key)
                provider_label = "Google Imagen 3"
        except RuntimeError as exc:
            return ToolResult.error(str(exc))
        except Exception as exc:
            return ToolResult.error(f"Unexpected error: {exc}")

        saved: list[str] = []
        ts = int(time.time())
        for i, img_bytes in enumerate(raw_images):
            if output_path:
                p = Path(output_path)
                if len(raw_images) > 1:
                    p = p.with_stem(f"{p.stem}_{i + 1}")
            else:
                suffix = f"_{i + 1}" if len(raw_images) > 1 else ""
                p = ctx.cwd / f"generated_{ts}{suffix}.png"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(img_bytes)
            saved.append(str(p))

        if not saved:
            return ToolResult.error("Images were returned but could not be saved.")

        paths = "\n".join(saved)
        return ToolResult.ok(
            f"Generated {len(saved)} image(s) via {provider_label}:\n{paths}\n\n"
            "Call send_file_to_telegram to send to the user."
        )
