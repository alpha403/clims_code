"""Server routing tests using a monkeypatched provider (no network)."""
import json
import threading
import urllib.request
from contextlib import contextmanager

from clims_core.providers.base import StreamEvent
import clims_core.providers as providers_pkg
from clims_server.api import create_server
from tests.fake_provider import FakeProvider


@contextmanager
def running_server(monkeypatch_provider):
    # force get_provider to return our fake regardless of name
    orig = providers_pkg.get_provider
    providers_pkg.get_provider = lambda name: monkeypatch_provider
    import clims_server.api as api_mod
    api_mod.get_provider = lambda name: monkeypatch_provider
    srv = create_server("127.0.0.1", 0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield port
    finally:
        srv.shutdown()
        providers_pkg.get_provider = orig


def _post(port, path, body):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=10)


def _get(port, path):
    return urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10)


def test_health_and_session_flow():
    fake = FakeProvider([
        [StreamEvent.text_delta("hi from server"), StreamEvent.usage(5, 2),
         StreamEvent.finished("end_turn")],
    ])
    with running_server(fake) as port:
        # health
        h = json.loads(_get(port, "/healthz").read())
        assert h["status"] == "ok"
        # create session
        sid = json.loads(_post(port, "/v1/sessions", {}).read())["session_id"]
        assert sid.startswith("sess_")
        # send a message, read SSE
        resp = _post(port, f"/v1/sessions/{sid}/messages", {
            "provider": "fake", "model": "fake", "api_key": "x",
            "message": "hello", "permission_mode": "bypass",
        })
        raw = resp.read().decode()
        assert "event: text_delta" in raw
        assert "hi from server" in raw
        assert "event: done" in raw
        # history persisted
        hist = json.loads(_get(port, f"/v1/sessions/{sid}").read())
        assert any(m["role"] == "assistant" for m in hist["messages"])


def test_missing_key_rejected():
    fake = FakeProvider([[StreamEvent.finished("end_turn")]])
    with running_server(fake) as port:
        sid = json.loads(_post(port, "/v1/sessions", {}).read())["session_id"]
        try:
            _post(port, f"/v1/sessions/{sid}/messages",
                  {"provider": "fake", "model": "fake", "message": "x"})
            assert False, "should have 400'd"
        except urllib.error.HTTPError as e:
            assert e.code == 400
