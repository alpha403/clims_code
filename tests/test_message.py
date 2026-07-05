from clims_core.agent.message import (
    Message, TextBlock, ToolUseBlock, ToolResultBlock,
)


def test_user_and_text_helpers():
    m = Message.user("hello")
    assert m.role == "user"
    assert m.text() == "hello"


def test_tool_uses_filter():
    m = Message(role="assistant", content=[
        TextBlock("let me run that"),
        ToolUseBlock(id="t1", name="bash", input={"command": "ls"}),
    ])
    assert m.text() == "let me run that"
    tus = m.tool_uses()
    assert len(tus) == 1 and tus[0].name == "bash"


def test_round_trip_serialization():
    m = Message(role="tool", content=[
        ToolResultBlock(tool_use_id="t1", content="ok", is_error=False),
    ])
    d = m.to_dict()
    m2 = Message.from_dict(d)
    assert m2.role == "tool"
    assert isinstance(m2.content[0], ToolResultBlock)
    assert m2.content[0].tool_use_id == "t1"
    assert m2.content[0].content == "ok"
