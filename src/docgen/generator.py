"""Core documentation generation, independent of the web API."""

from __future__ import annotations

import logging
import re
import time

import httpx
import ollama

from docgen.client import get_client
from docgen.config import Settings
from docgen.prompts import build_messages

logger = logging.getLogger(__name__)

# qwen3 and other reasoning models may emit <think>...</think> before the answer.
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


class DocGenerationError(RuntimeError):
    """Raised when the model cannot produce documentation."""


def generate_docs(
    code: str,
    language: str | None = None,
    settings: Settings | None = None,
) -> str:
    """Generate Markdown documentation for ``code``.

    Raises ``ValueError`` for empty input and ``DocGenerationError`` when the
    Ollama server is unreachable or returns an error.
    """
    if not code or not code.strip():
        raise ValueError("Code input cannot be empty.")

    settings = settings or Settings.load()
    client = get_client(settings.ollama_host, settings.timeout)

    logger.debug(
        "Requesting docs: model=%s host=%s language=%s chars=%d",
        settings.model,
        settings.ollama_host,
        language,
        len(code),
    )
    started = time.perf_counter()
    try:
        response = client.chat(
            model=settings.model,
            messages=build_messages(code, language),
        )
    except ollama.ResponseError as exc:
        logger.error("Ollama returned an error: %s", exc)
        raise DocGenerationError(f"Ollama error: {exc.error}") from exc
    except (httpx.HTTPError, ConnectionError) as exc:
        logger.error("Could not reach Ollama at %s: %s", settings.ollama_host, exc)
        raise DocGenerationError(f"Could not reach Ollama at {settings.ollama_host}") from exc

    content = response["message"]["content"] or ""
    documentation = _THINK_BLOCK.sub("", content).strip()
    logger.info(
        "Generated docs with %s in %.2fs (%d chars)",
        settings.model,
        time.perf_counter() - started,
        len(documentation),
    )
    if not documentation:
        raise DocGenerationError("Model returned an empty response.")
    return documentation
