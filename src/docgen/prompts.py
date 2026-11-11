"""Prompt construction for each language and output format."""

from __future__ import annotations

import re
from typing import Literal

from docgen.languages import GENERIC, Language, get_language

OutputFormat = Literal["markdown", "inline"]
OUTPUT_FORMATS: tuple[str, ...] = ("markdown", "inline")

_MARKDOWN_TEMPLATE = """You are an expert {name} technical writer.
Write concise Markdown reference documentation for the given {name} code.

Rules:
- Start with a one-paragraph overview.
- Add a ## section per public function, class or method, with Parameters, Returns and \
Errors where applicable.
- Use {name} terminology and types as they appear in the code.
- Include one short usage example in a ```{fence} fenced block.
- Output only the Markdown. No preamble, no closing remarks."""

_INLINE_TEMPLATE = """You are an expert {name} developer.
Add documentation comments to the given {name} code using {doc_style}.

Style rules:
{style_rules}

Output rules:
- Return the complete code with the documentation comments added, ready to paste over \
the original.
- Do not change, reorder, reformat or remove any existing code or comments.
- Document every public function, method, class and type; skip trivial private helpers.
- Output only the code. No Markdown fences, no explanation before or after."""


def system_prompt(language: Language, output_format: OutputFormat = "markdown") -> str:
    """Return the system prompt for a language and output format."""
    name = "software" if language is GENERIC else language.name
    if output_format == "markdown":
        fence = "" if language is GENERIC else language.key
        return _MARKDOWN_TEMPLATE.format(name=name, fence=fence)
    if output_format == "inline":
        return _INLINE_TEMPLATE.format(
            name=name, doc_style=language.doc_style, style_rules=language.style_rules
        )
    raise ValueError(
        f"Unknown output_format '{output_format}'. Use one of: {', '.join(OUTPUT_FORMATS)}."
    )


def build_messages(
    code: str,
    language: Language | str | None = None,
    output_format: OutputFormat = "markdown",
) -> list[dict[str, str]]:
    """Return the chat messages sent to the model for ``code``.

    ``language`` may be a :class:`Language`, a key or alias such as ``"rust"``,
    or ``None`` for the generic prompt.
    """
    if isinstance(language, str):
        language = get_language(language)
    return [
        {"role": "system", "content": system_prompt(language or GENERIC, output_format)},
        {"role": "user", "content": code},
    ]


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
_OUTER_FENCE = re.compile(r"^```[\w+#.-]*\s*\n(.*)\n```\s*$", re.DOTALL)


def clean_output(text: str, output_format: OutputFormat = "markdown") -> str:
    """Tidy raw model output.

    Removes ``<think>`` blocks that reasoning models such as qwen3 emit, and for
    inline output strips a single wrapping code fence so the result is paste-ready.
    """
    text = _THINK_BLOCK.sub("", text).strip()
    if output_format == "inline":
        match = _OUTER_FENCE.match(text)
        if match:
            text = match.group(1)
    return text
