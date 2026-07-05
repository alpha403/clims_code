"""Slash-command autocomplete (the /-popup)."""
import pytest

from clims_cli.prompt import SlashCompleter, Input, prompt_toolkit_available

pt = pytest.mark.skipif(not prompt_toolkit_available(), reason="prompt_toolkit not installed")


@pt
def test_completer_suggests_matching_commands():
    from prompt_toolkit.document import Document
    c = SlashCompleter({"/memory": "m", "/model": "mo", "/mode": "md", "/help": "h"})
    comps = [x.text for x in c.get_completions(Document("/m"), None)]
    assert "/memory" in comps and "/model" in comps and "/mode" in comps
    assert "/help" not in comps  # doesn't start with /m


@pt
def test_completer_only_for_slash_first_word():
    from prompt_toolkit.document import Document
    c = SlashCompleter({"/help": "h"})
    assert list(c.get_completions(Document("hello"), None)) == []      # not a slash command
    assert list(c.get_completions(Document("/help "), None)) == []     # command already typed


@pt
def test_completer_shows_descriptions():
    from prompt_toolkit.document import Document
    c = SlashCompleter({"/research": "deep web research"})
    comp = next(c.get_completions(Document("/res"), None))
    assert comp.text == "/research"
    assert "research" in str(comp.display_meta)


def test_input_falls_back_without_tty():
    # in the test process stdin is not a TTY -> uses stdlib input(), commands arg accepted
    i = Input(vim=False, commands={"/help": "x"})
    assert i.vim is False
