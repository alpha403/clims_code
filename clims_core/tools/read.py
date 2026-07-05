"""read tool — read text files, with PDF text extraction and image/binary handling."""
from __future__ import annotations

import shutil
import subprocess

from clims_core.permissions.policy import PermissionClass
from clims_core.tools.base import Tool, ToolContext, ToolResult

MAX_LINE_LEN = 2000
DEFAULT_LIMIT = 2000
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}


def _read_pdf(target) -> ToolResult:
    # Prefer pypdf (pure-Python, bundleable via [full]); fall back to the pdftotext binary.
    try:
        import pypdf
        reader = pypdf.PdfReader(str(target))
        text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
        return ToolResult.ok(
            text[:60000] or "(PDF has no extractable text — may be scanned images)")
    except ImportError:
        pass
    except Exception as e:
        return ToolResult.error(f"read: pypdf failed on {target.name}: {e}")
    if shutil.which("pdftotext"):
        try:
            proc = subprocess.run(["pdftotext", "-layout", str(target), "-"],
                                  capture_output=True, text=True, timeout=60)
            text = (proc.stdout or "").strip()
            return ToolResult.ok(text[:60000] or "(PDF has no extractable text)")
        except Exception as e:
            return ToolResult.error(f"read: pdftotext failed: {e}")
    return ToolResult.error(
        f"read: {target.name} is a PDF. Install pypdf (pip install clims_code[full]) "
        f"or poppler to extract its text.")


_IMAGE_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
MAX_IMAGE_BYTES = 5_000_000


def _image_note(target) -> ToolResult:
    """Return the actual image so a vision model can SEE it (image-in-tool-result)."""
    import base64
    media = _IMAGE_MEDIA.get(target.suffix.lower())
    size = target.stat().st_size if target.exists() else 0
    note = f"[image: {target.name}, {target.suffix.lstrip('.').upper()}, {size} bytes]"
    if media is None or size > MAX_IMAGE_BYTES:
        return ToolResult.ok(note + " (too large or unsupported for inline vision)")
    try:
        data = base64.b64encode(target.read_bytes()).decode("ascii")
    except OSError as e:
        return ToolResult.error(f"read: {e}")
    return ToolResult.ok(note, images=[{"media_type": media, "data": data}])


def _looks_binary(path) -> bool:
    try:
        with open(path, "rb") as f:
            return b"\x00" in f.read(2048)
    except OSError:
        return False


class ReadTool(Tool):
    name = "read"
    description = (
        "Read a UTF-8 text file from the local filesystem. Returns content with "
        "1-based line numbers. Use offset/limit for large files."
    )
    permission = PermissionClass.READ_ONLY
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute or cwd-relative file path."},
            "offset": {"type": "integer", "description": "1-based line to start from."},
            "limit": {"type": "integer", "description": "Max lines to read (default 2000)."},
        },
        "required": ["path"],
    }

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        path = input.get("path")
        if not path:
            return ToolResult.error("read: 'path' is required")
        target = ctx.resolve(path)
        if not target.exists():
            return ToolResult.error(f"read: file not found: {target}")
        if target.is_dir():
            try:
                entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            except OSError as e:
                return ToolResult.error(f"read: {e}")
            lines = [(f"{p.name}/" if p.is_dir() else p.name) for p in entries[:500]]
            more = f"\n… ({len(entries) - 500} more)" if len(entries) > 500 else ""
            return ToolResult.ok(f"Directory {target} ({len(entries)} entries):\n"
                                 + "\n".join(lines) + more if lines else f"{target} is empty")

        suffix = target.suffix.lower()
        if suffix == ".pdf":
            ctx.mark_read(target)
            return _read_pdf(target)
        if suffix in IMAGE_EXTS:
            ctx.mark_read(target)
            return _image_note(target)
        if _looks_binary(target):
            ctx.mark_read(target)
            return ToolResult.ok(f"[binary file: {target.name}, "
                                 f"{target.stat().st_size} bytes — not shown as text]")
        try:
            raw = target.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return ToolResult.error(f"read: {e}")

        lines = raw.splitlines()
        offset = max(1, int(input.get("offset", 1)))
        limit = int(input.get("limit", DEFAULT_LIMIT))
        chunk = lines[offset - 1: offset - 1 + limit]
        numbered = []
        for i, line in enumerate(chunk, start=offset):
            if len(line) > MAX_LINE_LEN:
                line = line[:MAX_LINE_LEN] + " …[truncated]"
            numbered.append(f"{i:6d}\t{line}")
        ctx.mark_read(target)  # track for read-before-edit
        body = "\n".join(numbered)
        if not body:
            return ToolResult.ok("(empty file)")
        more = ""
        if offset - 1 + limit < len(lines):
            more = f"\n… ({len(lines) - (offset - 1 + limit)} more lines; use offset)"
        return ToolResult.ok(body + more)
