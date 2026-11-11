import ollama


def test_root_reports_model(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["model"] == "test-model"


def test_generate_docs(client, fake_ollama):
    resp = client.post("/generate-docs", json={"code": "def f(): pass"})
    assert resp.status_code == 200
    assert resp.json() == {
        "documentation": "# Docs\n\nAdds two numbers.",
        "language": "python",
        "language_source": "content",
        "output_format": "markdown",
    }
    assert len(fake_ollama.calls) == 1


def test_empty_code_is_400(client):
    resp = client.post("/generate-docs", json={"code": "  "})
    assert resp.status_code == 400


def test_missing_code_is_422(client):
    assert client.post("/generate-docs", json={}).status_code == 422


def test_ollama_error_is_502(client, fake_ollama):
    fake_ollama.error = ollama.ResponseError("model not found", 404)
    resp = client.post("/generate-docs", json={"code": "x = 1"})
    assert resp.status_code == 502
    assert "model not found" in resp.json()["detail"]


def test_generate_inline_with_filename(client, fake_ollama):
    fake_ollama.reply = "```go\n// Add adds.\nfunc Add() {}\n```"
    resp = client.post(
        "/generate-docs",
        json={"code": "func Add() {}", "filename": "a.go", "output_format": "inline"},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "documentation": "// Add adds.\nfunc Add() {}",
        "language": "go",
        "language_source": "filename",
        "output_format": "inline",
    }


def test_unknown_language_is_400(client, fake_ollama):
    resp = client.post("/generate-docs", json={"code": "x", "language": "cobol"})
    assert resp.status_code == 400
    assert "Unsupported language" in resp.json()["detail"]
    assert fake_ollama.calls == []


def test_bad_output_format_is_422(client):
    resp = client.post("/generate-docs", json={"code": "x", "output_format": "html"})
    assert resp.status_code == 422


def test_languages_endpoint(client):
    keys = {lang["key"] for lang in client.get("/languages").json()}
    assert {"python", "javascript", "typescript", "java", "go", "rust"} <= keys
