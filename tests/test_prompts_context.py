from docgen.prompts import build_messages


def test_context_is_prepended_and_optional():
    plain = build_messages("x = 1", "python")
    assert plain[1]["content"] == "x = 1"
    with_ctx = build_messages("x = 1", "python", context="Part 2 of 3 of `a.py`.")
    assert with_ctx[1]["content"] == "Part 2 of 3 of `a.py`.\n\nx = 1"
    assert with_ctx[0] == plain[0]
