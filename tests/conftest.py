from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from docgen.api import create_app
from docgen.client import get_client
from docgen.config import Settings


class FakeOllamaClient:
    """Stands in for ollama.Client; records calls and returns a canned reply."""

    def __init__(self, reply: str = "# Docs\n\nAdds two numbers.") -> None:
        self.reply = reply
        self.error: Exception | None = None
        self.calls: list[dict[str, Any]] = []

    def chat(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return {"message": {"role": "assistant", "content": self.reply}}


@pytest.fixture
def settings() -> Settings:
    return Settings(model="test-model", ollama_host="http://ollama.test:11434", timeout=5)


@pytest.fixture
def fake_ollama(monkeypatch: pytest.MonkeyPatch) -> FakeOllamaClient:
    fake = FakeOllamaClient()
    monkeypatch.setattr("docgen.generator.get_client", lambda host, timeout: fake)
    return fake


@pytest.fixture
def client(settings: Settings, fake_ollama: FakeOllamaClient) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture(autouse=True)
def _clear_client_cache():
    yield
    get_client.cache_clear()
