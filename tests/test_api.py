import pytest
from fastapi.testclient import TestClient

import main


class FakeClient:
    calls = []

    def __init__(self, host=None):
        pass

    def chat(self, model, messages):
        FakeClient.calls.append(messages)
        return {"message": {"content": "<think>ok</think>```go\n// Add adds.\nfunc Add() {}\n```"}}


@pytest.fixture
def client(monkeypatch):
    FakeClient.calls = []
    monkeypatch.setattr(main.ollama, "Client", FakeClient)
    return TestClient(main.app)


def test_generate_inline_with_filename(client):
    r = client.post("/generate-docs", json={"code": "func Add() {}", "filename": "a.go", "output_format": "inline"})
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "documentation": "// Add adds.\nfunc Add() {}",
        "language": "go",
        "language_source": "filename",
        "output_format": "inline",
    }
    assert "Go doc comments" in FakeClient.calls[0][0]["content"]


def test_generate_defaults_to_markdown_and_detects(client):
    r = client.post("/generate-docs", json={"code": "def f():\n    pass\n"})
    assert r.status_code == 200
    assert r.json()["language"] == "python"
    assert r.json()["output_format"] == "markdown"


def test_unknown_language_is_400(client):
    r = client.post("/generate-docs", json={"code": "x", "language": "cobol"})
    assert r.status_code == 400
    assert "Unsupported language" in r.json()["detail"]


def test_bad_format_is_422(client):
    assert client.post("/generate-docs", json={"code": "x", "output_format": "html"}).status_code == 422


def test_empty_code_is_400(client):
    assert client.post("/generate-docs", json={"code": "  "}).status_code == 400


def test_languages_endpoint(client):
    keys = [l["key"] for l in client.get("/languages").json()]
    assert {"python", "javascript", "java", "go", "rust"} <= set(keys)
