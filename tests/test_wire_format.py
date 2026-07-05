"""Verify each adapter builds the correct provider wire format from normalized
messages. This is the core proof that the abstraction handles two dialects."""
import json

from clims_core.agent.message import (
    Message, TextBlock, ToolUseBlock, ToolResultBlock,
)
from clims_core.providers.base import ToolSchema
from clims_core.providers.deepseek import DeepSeekProvider
from clims_core.providers.anthropic import AnthropicProvider

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


def test_deepseek_wire():
    p = DeepSeekProvider()
    msgs = p._messages_wire(_conversation(), system="be nice")
    # system hoisted as first message
    assert msgs[0] == {"role": "system", "content": "be nice"}
    # assistant carries tool_calls with JSON-string arguments
    asst = next(m for m in msgs if m["role"] == "assistant")
    assert asst["tool_calls"][0]["function"]["name"] == "bash"
    assert json.loads(asst["tool_calls"][0]["function"]["arguments"]) == {"command": "ls"}
    # tool result becomes a role:tool message
    tool_msg = next(m for m in msgs if m["role"] == "tool")
    assert tool_msg["tool_call_id"] == "t1"
    assert tool_msg["content"] == "a.txt"
    # tools wire shape
    tw = p._tools_wire([TOOL])
    assert tw[0]["type"] == "function"
    assert tw[0]["function"]["name"] == "bash"


def test_anthropic_wire():
    p = AnthropicProvider()
    msgs = p._messages_wire(_conversation())
    # assistant content is a block list with text + tool_use
    asst = next(m for m in msgs if m["role"] == "assistant")
    types = [b["type"] for b in asst["content"]]
    assert "text" in types and "tool_use" in types
    tu = next(b for b in asst["content"] if b["type"] == "tool_use")
    assert tu["input"] == {"command": "ls"}
    # tool result is carried inside a USER message as tool_result block
    user_with_result = [m for m in msgs if m["role"] == "user"]
    blocks = [b for m in user_with_result for b in m["content"] if isinstance(b, dict)]
    assert any(b.get("type") == "tool_result" and b.get("tool_use_id") == "t1" for b in blocks)
    # tools wire shape (input_schema, not function wrapper)
    tw = p._tools_wire([TOOL])
    assert tw[0]["name"] == "bash" and "input_schema" in tw[0]
