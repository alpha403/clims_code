"""web_search HTML parser tests (deterministic, no network)."""
from clims_core.tools.web_search import parse_ddg_html

SAMPLE = """
<div class="result results_links">
  <h2 class="result__title">
    <a rel="nofollow" class="result__a"
       href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpython&amp;rut=abc">
       Python <b>Official</b> Site</a>
  </h2>
  <a class="result__snippet" href="x">The official home of the <b>Python</b> language.</a>
</div>
<div class="result results_links">
  <h2 class="result__title">
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fdocs.python.org%2F3%2F">
       Python 3 Docs</a>
  </h2>
  <a class="result__snippet" href="y">Documentation for Python 3.</a>
</div>
"""


def test_parse_extracts_title_url_snippet():
    results = parse_ddg_html(SAMPLE)
    assert len(results) == 2
    assert results[0]["title"] == "Python Official Site"
    assert results[0]["url"] == "https://example.com/python"
    assert "official home" in results[0]["snippet"].lower()
    assert results[1]["url"] == "https://docs.python.org/3/"


def test_parse_respects_max_results():
    assert len(parse_ddg_html(SAMPLE, max_results=1)) == 1


def test_parse_empty_html():
    assert parse_ddg_html("<html>nothing</html>") == []


def test_websearch_tool_registered():
    from clims_core.tools import default_tools
    names = {t.name for t in default_tools()}
    assert "web_search" in names
