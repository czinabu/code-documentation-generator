"""Core documentation generation, independent of the web API."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx
import ollama

from docgen.client import get_client
from docgen.config import Settings
from docgen.languages import Language, detect_language
from docgen.prompts import OutputFormat, build_messages, clean_output

logger = logging.getLogger(__name__)


class DocGenerationError(RuntimeError):
    """Raised when the model cannot produce documentation."""


@dataclass(frozen=True)
class DocResult:
    documentation: str
    language: Language
    language_source: str
    output_format: OutputFormat


def generate(
    code: str,
    language: str | None = None,
    filename: str | None = None,
    output_format: OutputFormat = "markdown",
    settings: Settings | None = None,
    *,
    context: str | None = None,
) -> DocResult:
    """Generate documentation for ``code`` and report which language was used.

    The language comes from ``language`` (a key or alias), else the extension of
    ``filename``, else a guess from the code. ``output_format`` is ``"markdown"``
    for a reference summary or ``"inline"`` for the code with native doc comments.
    ``context`` is an optional note for the model placed before the code.

    Raises ``ValueError`` for empty input or an unsupported ``language``, and
    ``DocGenerationError`` when the Ollama server is unreachable or returns an error.
    """
    if not code or not code.strip():
        raise ValueError("Code input cannot be empty.")

    lang, source = detect_language(code, language, filename)
    messages = build_messages(code, lang, output_format, context=context)

    settings = settings or Settings.load()
    client = get_client(settings.ollama_host, settings.timeout)

    logger.debug(
        "Requesting docs: model=%s host=%s language=%s (%s) format=%s chars=%d",
        settings.model,
        settings.ollama_host,
        lang.key,
        source,
        output_format,
        len(code),
    )
    started = time.perf_counter()
    try:
        response = client.chat(model=settings.model, messages=messages)
    except ollama.ResponseError as exc:
        logger.error("Ollama returned an error: %s", exc)
        raise DocGenerationError(f"Ollama error: {exc.error}") from exc
    except (httpx.HTTPError, ConnectionError) as exc:
        logger.error("Could not reach Ollama at %s: %s", settings.ollama_host, exc)
        raise DocGenerationError(f"Could not reach Ollama at {settings.ollama_host}") from exc

    documentation = clean_output(response["message"]["content"] or "", output_format)
    logger.info(
        "Generated %s %s docs with %s in %.2fs (%d chars)",
        lang.key,
        output_format,
        settings.model,
        time.perf_counter() - started,
        len(documentation),
    )
    if not documentation:
        raise DocGenerationError("Model returned an empty response.")
    return DocResult(documentation, lang, source, output_format)


def generate_docs(
    code: str,
    language: str | None = None,
    filename: str | None = None,
    output_format: OutputFormat = "markdown",
    settings: Settings | None = None,
    *,
    context: str | None = None,
) -> str:
    """Generate documentation for ``code`` and return it as a string.

    Same arguments and errors as :func:`generate`.
    """
    return generate(
        code, language, filename, output_format, settings, context=context
    ).documentation
