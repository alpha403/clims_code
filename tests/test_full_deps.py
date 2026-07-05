"""Optional [full] deps: tiktoken token counting + pypdf PDF extraction."""
import importlib.util
from pathlib import Path

import pytest

from clims_core.agent.compaction import estimate_tokens
from clims_core.agent.message import Message
from clims_core.tools import ReadTool
from clims_core.tools.base import ToolContext

HAS_TIKTOKEN = importlib.util.find_spec("tiktoken") is not None
HAS_PYPDF = importlib.util.find_spec("pypdf") is not None


def _valid_pdf(text: str) -> bytes:
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>",
        None,  # contents, filled below
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    content = b"BT /F1 24 Tf 20 100 Td (%s) Tj ET" % text.encode()
    objs[3] = b"<</Length %d>>stream\n%s\nendstream" % (len(content), content)

    pdf = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n%s\nendobj\n" % (i, body)
    xref_off = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        pdf += b"%010d 00000 n \n" % off
    pdf += b"trailer\n<</Root 1 0 R/Size %d>>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref_off)
    return pdf


@pytest.mark.skipif(not HAS_TIKTOKEN, reason="tiktoken not installed")
def test_tiktoken_is_used():
    # "hello world " is 2 tokens; *5 ≈ 10-11, much less than the chars/4 estimate of ~15
    n = estimate_tokens([Message.user("hello world " * 5)])
    assert 8 <= n <= 13


@pytest.mark.skipif(not HAS_PYPDF, reason="pypdf not installed")
def test_pypdf_extracts_text(tmp_path: Path):
    (tmp_path / "doc.pdf").write_bytes(_valid_pdf("Hello PDF World"))
    res = ReadTool().run({"path": "doc.pdf"}, ToolContext(cwd=tmp_path))
    assert not res.is_error
    assert "Hello PDF World" in res.content
