"""Gemini wire-format tests — verifies the functionCall/functionResponse dialect."""
from clims_core.agent.message import Message, TextBlock, ToolUseBlock, ToolResultBlock
from clims_core.providers import get_provider
from clims_core.providers.base import ToolSchema
from clims_core.providers.gemini import GeminiProvider

TOOL = ToolSchema(name="bash", description="run", input_schema={"type": "object"})


def _conversation():
    return [
        Message.user("list files"),
        Message(role="assistant", content=[
            TextBlock("running"),
            ToolUseBlock(id="t1", name="bash", input={"command": "ls"}),
        ]),
        Message.tool_results([ToolResultBlock(tool_use_id="t1", content="a.txt")]),
    ]


def test_gemini_registered():
    assert get_provider("gemini") is not None


def test_gemini_contents_wire():
    p = GeminiProvider()
    contents = p._contents_wire(_conversation())
    # user prompt
    assert contents[0]["role"] == "user"
    assert contents[0]["parts"][0]["text"] == "list files"
    # assistant -> role "model" with functionCall part
    model_turn = next(c for c in contents if c["role"] == "model")
    fc = next(p_ for p_ in model_turn["parts"] if "functionCall" in p_)["functionCall"]
    assert fc["name"] == "bash" and fc["args"] == {"command": "ls"}
    # tool result -> functionResponse matched by NAME (not id)
    resp_part = None
    for c in contents:
        for prt in c["parts"]:
            if "functionResponse" in prt:
                resp_part = prt["functionResponse"]
    assert resp_part is not None
    assert resp_part["name"] == "bash"  # recovered from the prior functionCall
    assert resp_part["response"] == {"result": "a.txt"}


def test_gemini_tools_and_system_wire():
    p = GeminiProvider()
    tw = p._tools_wire([TOOL])
    assert "functionDeclarations" in tw[0]
    assert tw[0]["functionDeclarations"][0]["name"] == "bash"
    # header carries the key, not the URL
    assert p._headers("KEY")["x-goog-api-key"] == "KEY"


def test_gemini_capabilities():
    caps = GeminiProvider().capabilities("gemini-1.5-pro")
    assert caps.context_window >= 1000000 and caps.supports_vision
