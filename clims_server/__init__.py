"""clims_server — stdlib HTTP API exposing the clims_code engine.

Zero external deps (ThreadingHTTPServer + SSE). Intended to sit behind a reverse
proxy (nginx/Caddy) for TLS and scale. BYOK: the provider key arrives in each
request body, is used in-memory only, and is never logged or persisted.
"""
from clims_server.api import create_server, serve

__all__ = ["create_server", "serve"]
