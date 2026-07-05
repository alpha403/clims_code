"""Batch 4: devtools helpers + Bedrock/Vertex routing structure."""
import os

from clims_core.devtools import review_prompt, bug_report
from clims_core.providers import get_provider, available_providers
from clims_core.providers.bedrock import BedrockAnthropicProvider
from clims_core.providers.vertex import VertexAnthropicProvider


def test_review_prompt():
    assert review_prompt("") == ""
    rp = review_prompt("@@ -1 +1 @@\n-old\n+new")
    assert "code reviewer" in rp and "+new" in rp


def test_bug_report_has_env_and_transcript():
    rep = bug_report("deepseek", "deepseek-chat", "user: hi\nassistant: hello")
    assert "bug report" in rep.lower()
    assert "deepseek:deepseek-chat" in rep and "hello" in rep


def test_bedrock_vertex_registered():
    for n in ("bedrock", "vertex"):
        assert n in available_providers()
        assert get_provider(n) is not None


def test_bedrock_endpoint(monkeypatch):
    monkeypatch.setenv("CLIMS_BEDROCK_REGION", "us-west-2")
    p = BedrockAnthropicProvider()
    url = p.endpoint("anthropic.claude-3-sonnet")
    assert url == ("https://bedrock-runtime.us-west-2.amazonaws.com/"
                   "model/anthropic.claude-3-sonnet/invoke")


def test_vertex_endpoint(monkeypatch):
    monkeypatch.setenv("CLIMS_VERTEX_PROJECT", "my-proj")
    monkeypatch.setenv("CLIMS_VERTEX_REGION", "us-east5")
    p = VertexAnthropicProvider()
    url = p.endpoint("claude-3-5-sonnet")
    assert "projects/my-proj" in url and "publishers/anthropic/models/claude-3-5-sonnet:rawPredict" in url


def test_bedrock_requires_aws_creds(monkeypatch):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    from clims_core.agent.message import Message
    from clims_core.providers.base import ProviderError
    p = BedrockAnthropicProvider()
    try:
        list(p.chat(model="m", messages=[Message.user("hi")], api_key=""))
        assert False, "should raise"
    except ProviderError:
        pass
