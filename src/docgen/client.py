"""A single shared Ollama client per (host, timeout) pair."""

from __future__ import annotations

from functools import lru_cache

import ollama


@lru_cache(maxsize=8)
def get_client(host: str, timeout: float) -> ollama.Client:
    """Return a cached client so connections are reused across requests."""
    return ollama.Client(host=host, timeout=timeout)
