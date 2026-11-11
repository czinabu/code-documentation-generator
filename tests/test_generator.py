import httpx
import ollama
import pytest

from docgen.client import get_client
from docgen.generator import DocGenerationError, generate, generate_docs
from docgen.languages import UnknownLanguageError, get_language
from docgen.prompts import system_prompt


def test_generate_docs_sends_prompt(fake_ollama, settings):
    result = generate_docs("def add(a, b):\n    return a + b", settings=settings)
    assert result == "# Docs\n\nAdds two numbers."
    (call,) = fake_ollama.calls
    assert call["model"] == "test-model"
    assert call["messages"][0] == {
        "role": "system",
        "content": system_prompt(get_language("python"), "markdown"),
    }
    assert call["messages"][1]["content"] == "def add(a, b):\n    return a + b"


def test_language_hint_selects_prompt(fake_ollama, settings):
    generate_docs("fn main() {}", language="Rust", settings=settings)
    assert "```rust" in fake_ollama.calls[0]["messages"][0]["content"]


def test_generate_reports_language_and_cleans_inline(fake_ollama, settings):
    fake_ollama.reply = "<think>x</think>```go\n// Add adds.\nfunc Add() {}\n```"
    result = generate("func Add() {}", filename="a.go", output_format="inline", settings=settings)
    assert result.documentation == "// Add adds.\nfunc Add() {}"
    assert (result.language.key, result.language_source) == ("go", "filename")
    assert "Go doc comments" in fake_ollama.calls[0]["messages"][0]["content"]


def test_unknown_language_rejected_before_model_call(fake_ollama, settings):
    with pytest.raises(UnknownLanguageError):
        generate_docs("x", language="cobol", settings=settings)
    assert fake_ollama.calls == []


def test_strips_think_block(fake_ollama, settings):
    fake_ollama.reply = "<think>\nreasoning...\n</think>\n\n# Real docs"
    assert generate_docs("x = 1", settings=settings) == "# Real docs"


@pytest.mark.parametrize("code", ["", "   \n\t"])
def test_rejects_empty_code(fake_ollama, settings, code):
    with pytest.raises(ValueError):
        generate_docs(code, settings=settings)
    assert fake_ollama.calls == []


@pytest.mark.parametrize(
    "error",
    [
        ollama.ResponseError("model 'x' not found", 404),
        ConnectionError("refused"),
        httpx.ReadTimeout("timed out"),
    ],
)
def test_ollama_failures_become_generation_errors(fake_ollama, settings, error):
    fake_ollama.error = error
    with pytest.raises(DocGenerationError):
        generate_docs("x = 1", settings=settings)


def test_empty_model_reply_is_an_error(fake_ollama, settings):
    fake_ollama.reply = "<think>only thinking</think>"
    with pytest.raises(DocGenerationError):
        generate_docs("x = 1", settings=settings)


def test_client_is_reused():
    assert get_client("http://h:1", 5.0) is get_client("http://h:1", 5.0)
    assert get_client("http://h:1", 5.0) is not get_client("http://h:2", 5.0)
