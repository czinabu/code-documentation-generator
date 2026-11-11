import pytest

from docgen.languages import GENERIC, LANGUAGES, get_language
from docgen.prompts import build_messages, clean_output, system_prompt


@pytest.mark.parametrize("lang", LANGUAGES + (GENERIC,), ids=lambda lang: lang.key)
@pytest.mark.parametrize("fmt", ["markdown", "inline"])
def test_every_language_builds_both_formats(lang, fmt):
    msgs = build_messages("x = 1", lang, fmt)
    assert [m["role"] for m in msgs] == ["system", "user"]
    assert msgs[1]["content"] == "x = 1"
    for placeholder in ("{name}", "{fence}", "{doc_style}", "{style_rules}"):
        assert placeholder not in msgs[0]["content"]


@pytest.mark.parametrize(
    "key,marker",
    [
        ("python", "docstring"),
        ("javascript", "@param {Type}"),
        ("java", "Javadoc"),
        ("go", "starts with the name"),
        ("rust", "///"),
    ],
)
def test_inline_prompt_uses_native_style(key, marker):
    assert marker in system_prompt(get_language(key), "inline")


def test_markdown_prompt_fences_with_language():
    assert "```rust" in system_prompt(get_language("rust"), "markdown")


def test_unknown_format():
    with pytest.raises(ValueError):
        system_prompt(get_language("python"), "html")


def test_clean_output_strips_think_and_fence():
    raw = '<think>\nhmm\n</think>\n```python\ndef f():\n    """Doc."""\n```'
    assert clean_output(raw, "inline") == 'def f():\n    """Doc."""'
    # Markdown output keeps its fences.
    assert (
        clean_output("<think>x</think># Title\n```py\n1\n```", "markdown")
        == "# Title\n```py\n1\n```"
    )


def test_build_messages_accepts_names_and_none():
    assert "Go doc comments" in build_messages("x", "golang", "inline")[0]["content"]
    assert "software" in build_messages("x")[0]["content"]
