import httpx
import ollama
import pytest

from docgen.client import get_client
from docgen.generator import DocGenerationError, generate_docs
from docgen.prompts import SYSTEM_PROMPT, build_messages


def test_generate_docs_sends_prompt(fake_ollama, settings):
    result = generate_docs("def add(a, b):\n    return a + b", settings=settings)
    assert result == "# Docs\n\nAdds two numbers."
    (call,) = fake_ollama.calls
    assert call["model"] == "test-model"
    assert call["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert call["messages"][1]["content"] == "def add(a, b):\n    return a + b"


def test_language_hint_included():
    messages = build_messages("fn main() {}", language="Rust")
    assert "Language: Rust" in messages[1]["content"]
    assert "```rust" in messages[1]["content"]


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
