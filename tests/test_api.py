import ollama


def test_root_reports_model(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["model"] == "test-model"


def test_generate_docs(client, fake_ollama):
    resp = client.post("/generate-docs", json={"code": "def f(): pass"})
    assert resp.status_code == 200
    assert resp.json() == {"documentation": "# Docs\n\nAdds two numbers."}
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
