"""Zero-dependency HTTP for provider adapters.

Uses only stdlib (urllib + ssl). Provides:
  - post_json(): a plain JSON POST returning parsed JSON.
  - post_sse():  a streaming POST yielding parsed Server-Sent Events.

No `requests`, no vendor SDKs. This file is the only place that touches the wire.
"""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterator


DEFAULT_TIMEOUT = 600  # seconds; long for slow model streams

# A standard, verified TLS context. Callers should not disable verification.
_SSL_CONTEXT = ssl.create_default_context()

# Proxy support: honor standard env vars (HTTP_PROXY/HTTPS_PROXY/NO_PROXY) plus an
# explicit CLIMS_PROXY override. urllib reads env proxies by default; we install an
# opener so CLIMS_PROXY (if set) is also respected.
import os as _os  # noqa: E402


def _install_proxy_opener():
    explicit = _os.environ.get("CLIMS_PROXY")
    if explicit:
        handler = urllib.request.ProxyHandler({"http": explicit, "https": explicit})
        urllib.request.install_opener(urllib.request.build_opener(handler))


_install_proxy_opener()


class HTTPError(Exception):
    def __init__(self, status: int, body: str, url: str):
        self.status = status
        self.body = body
        self.url = url
        super().__init__(f"HTTP {status} from {url}: {body[:500]}")


@dataclass
class SSEMessage:
    event: str | None
    data: str


def _build_request(url: str, headers: dict, body: dict | None, method: str = "POST") -> urllib.request.Request:
    raw = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=raw, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    return req


def post_json(
    url: str,
    headers: dict,
    body: dict,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    """POST JSON, return parsed JSON. Raises HTTPError on non-2xx."""
    req = _build_request(url, headers, body)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data) if data else {}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise HTTPError(e.code, body_text, url) from None
    except urllib.error.URLError as e:
        raise HTTPError(0, f"connection error: {e.reason}", url) from None


def get_json(url: str, headers: dict, timeout: float = DEFAULT_TIMEOUT) -> dict:
    req = _build_request(url, headers, None, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data) if data else {}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise HTTPError(e.code, body_text, url) from None
    except urllib.error.URLError as e:
        raise HTTPError(0, f"connection error: {e.reason}", url) from None


def post_raw(url: str, headers: dict, data: bytes, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """POST pre-serialized bytes with exact headers, return parsed JSON. Needed
    when the body bytes must match a signature (e.g. AWS SigV4)."""
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        raise HTTPError(e.code, e.read().decode("utf-8", errors="replace"), url) from None
    except urllib.error.URLError as e:
        raise HTTPError(0, f"connection error: {e.reason}", url) from None


def get_text(url: str, headers: dict | None = None, timeout: float = 60,
             max_bytes: int = 5_000_000) -> tuple[str, str]:
    """GET a URL and return (content_type, text). For the web_fetch tool.

    Not JSON-specific. Decodes as utf-8 (best effort). Caps body size.
    """
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "clims_code/0.1 (+https://localhost)")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:
            ctype = resp.headers.get("Content-Type", "")
            raw = resp.read(max_bytes)
            return ctype, raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise HTTPError(e.code, body_text, url) from None
    except urllib.error.URLError as e:
        raise HTTPError(0, f"connection error: {e.reason}", url) from None


def post_form(url: str, fields: dict, headers: dict | None = None,
              timeout: float = 30, max_bytes: int = 5_000_000) -> tuple[str, str]:
    """POST application/x-www-form-urlencoded, return (content_type, text).

    For HTML endpoints that expect a form POST (e.g. DuckDuckGo's html search).
    """
    import urllib.parse
    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent",
                   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) clims_code/0.1")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:
            ctype = resp.headers.get("Content-Type", "")
            return ctype, resp.read(max_bytes).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise HTTPError(e.code, body_text, url) from None
    except urllib.error.URLError as e:
        raise HTTPError(0, f"connection error: {e.reason}", url) from None


def post_sse(
    url: str,
    headers: dict,
    body: dict,
    timeout: float = DEFAULT_TIMEOUT,
) -> Iterator[SSEMessage]:
    """POST and stream Server-Sent Events.

    Yields SSEMessage(event, data) per event block. `data` is the raw payload
    string (often JSON, sometimes the literal "[DONE]"). Multi-line data fields
    are joined with newlines per the SSE spec.
    """
    hdrs = dict(headers or {})
    hdrs.setdefault("Accept", "text/event-stream")
    req = _build_request(url, hdrs, body)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT)
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise HTTPError(e.code, body_text, url) from None
    except urllib.error.URLError as e:
        raise HTTPError(0, f"connection error: {e.reason}", url) from None

    with resp:
        event_name: str | None = None
        data_lines: list[str] = []
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
            if line == "":
                # dispatch accumulated event
                if data_lines:
                    yield SSEMessage(event=event_name, data="\n".join(data_lines))
                event_name = None
                data_lines = []
                continue
            if line.startswith(":"):
                continue  # comment / keep-alive
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].lstrip(" "))
            # other SSE fields (id:, retry:) ignored
        # flush a trailing event with no blank line after it
        if data_lines:
            yield SSEMessage(event=event_name, data="\n".join(data_lines))
