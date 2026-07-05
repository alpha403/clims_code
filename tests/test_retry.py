"""Tests for transient-failure retry in the provider streaming wrapper."""
from clims_core.providers.base import stream_with_retry, StreamEvent


def test_retries_transient_error_then_succeeds():
    calls = {"n": 0}

    def make_stream():
        calls["n"] += 1
        if calls["n"] == 1:
            # first attempt: transient error before any output
            yield StreamEvent.failure("read timeout")
            return
        yield StreamEvent.text_delta("hello")
        yield StreamEvent.finished("end_turn")

    events = list(stream_with_retry(make_stream, max_retries=2, base_delay=0))
    types = [e.type for e in events]
    # the transient error must have been swallowed and retried
    assert "error" not in types
    assert "text_delta" in types and "done" in types
    assert calls["n"] == 2


def test_retries_raised_exception():
    calls = {"n": 0}

    def make_stream():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("boom")
        yield StreamEvent.text_delta("ok")
        yield StreamEvent.finished("end_turn")

    events = list(stream_with_retry(make_stream, max_retries=3, base_delay=0))
    assert any(e.type == "text_delta" for e in events)
    assert calls["n"] == 3


def test_gives_up_after_max_retries():
    def make_stream():
        raise TimeoutError("always fails")
        yield  # unreachable

    events = list(stream_with_retry(make_stream, max_retries=2, base_delay=0))
    # exhausts retries -> surfaces a single error event, no crash
    assert len(events) == 1 and events[0].type == "error"


def test_no_retry_after_productive_output():
    calls = {"n": 0}

    def make_stream():
        calls["n"] += 1
        yield StreamEvent.text_delta("partial")
        raise TimeoutError("mid-stream")

    events = list(stream_with_retry(make_stream, max_retries=3, base_delay=0))
    # text already committed -> must NOT retry, surfaces error after the text
    assert calls["n"] == 1
    assert events[0].type == "text_delta"
    assert events[-1].type == "error"
