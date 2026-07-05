"""OpenAI-compatible /v1/chat/completions shim tests (no network)."""
import json
import threading
import urllib.request
from contextlib import contextmanager

from clims_core.providers.base import StreamEvent
import clims_server.api as api_mod
from clims_server.api import create_server
from tests.fake_provider import FakeProvider


@contextmanager
def running_server(fake):
    orig = api_mod.get_provider
    api_mod.get_provider = lambda name: fake
    srv = create_server("127.0.0.1", 0)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield port
    finally:
        srv.shutdown()
        api_mod.get_provider = orig


def _post(port, path, body, headers=None):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(),
        method="POST", headers={"Content-Type": "application/json", **(headers or {})})
    return urllib.request.urlopen(req, timeout=10)


def test_openai_nonstreaming_completion():
    fake = FakeProvider([[StreamEvent.text_delta("Hello from clims"),
                          StreamEvent.usage(7, 4), StreamEvent.finished("end_turn")]])
    with running_server(fake) as port:
        resp = _post(port, "/v1/chat/completions", {
            "model": "deepseek-chat",
            "messages": [{"role": "system", "content": "be nice"},
                         {"role": "user", "content": "hi"}],
        }, headers={"Authorization": "Bearer sk-test"})
        data = json.loads(resp.read())
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["content"] == "Hello from clims"
        assert data["usage"]["total_tokens"] == 11
        # system was hoisted, not sent as a normal message
        sent = fake.calls[0]
        assert all(m.role != "system" for m in sent)


def test_openai_requires_bearer_key():
    fake = FakeProvider([[StreamEvent.finished("end_turn")]])
    with running_server(fake) as port:
        try:
            _post(port, "/v1/chat/completions",
                  {"model": "x", "messages": [{"role": "user", "content": "hi"}]})
            assert False, "should 401"
        except urllib.error.HTTPError as e:
            assert e.code == 401


def test_openai_streaming_chunks():
    fake = FakeProvider([[StreamEvent.text_delta("a"), StreamEvent.text_delta("b"),
                          StreamEvent.finished("end_turn")]])
    with running_server(fake) as port:
        resp = _post(port, "/v1/chat/completions", {
            "model": "deepseek-chat", "stream": True,
            "messages": [{"role": "user", "content": "hi"}],
        }, headers={"Authorization": "Bearer sk-test"})
        raw = resp.read().decode()
        assert "chat.completion.chunk" in raw
        assert '"content": "a"' in raw and '"content": "b"' in raw
        assert "data: [DONE]" in raw
