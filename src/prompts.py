"""Prompt construction for each language and output format."""

from __future__ import annotations

import re
from typing import Dict, List, Literal

from languages import Language

OutputFormat = Literal["markdown", "inline"]
OUTPUT_FORMATS = ("markdown", "inline")

_MARKDOWN_TEMPLATE = """You are an expert {name} technical writer.
Write concise Markdown reference documentation for the given {name} code.

Rules:
- Start with a one-paragraph overview.
- Add a ## section per public function, class or method, with Parameters, Returns and Errors where applicable.
- Use {name} terminology and types as they appear in the code.
- Include one short usage example in a ```{fence} fenced block.
- Output only the Markdown. No preamble, no closing remarks."""

_INLINE_TEMPLATE = """You are an expert {name} developer.
Add documentation comments to the given {name} code using {doc_style}.

Style rules:
{style_rules}

Output rules:
- Return the complete code with the documentation comments added, ready to paste over the original.
- Do not change, reorder, reformat or remove any existing code or comments.
- Document every public function, method, class and type; skip trivial private helpers.
- Output only the code. No Markdown fences, no explanation before or after."""


def system_prompt(language: Language, output_format: OutputFormat = "markdown") -> str:
    """Return the system prompt for a language and output format."""
    if output_format == "markdown":
        fence = "" if language.key == "generic" else language.key
        return _MARKDOWN_TEMPLATE.format(name=_display(language), fence=fence)
    if output_format == "inline":
        return _INLINE_TEMPLATE.format(
            name=_display(language),
            doc_style=language.doc_style,
            style_rules=language.style_rules,
        )
    raise ValueError(f"Unknown output_format '{output_format}'. Use one of: {', '.join(OUTPUT_FORMATS)}.")


def build_messages(
    code: str,
    language: Language,
    output_format: OutputFormat = "markdown",
) -> List[Dict[str, str]]:
    """Build the chat messages to send to the model."""
    return [
        {"role": "system", "content": system_prompt(language, output_format)},
        {"role": "user", "content": code},
    ]


_THINK_BLOCK = re.compile(r"<think>.*?</think>\s*", re.S)
_OUTER_FENCE = re.compile(r"^```[\w+#.-]*\s*\n(.*)\n```\s*$", re.S)


def clean_output(text: str, output_format: OutputFormat = "markdown") -> str:
    """Tidy raw model output.

    Removes reasoning blocks that models such as Qwen3 emit, and for inline
    output strips a single wrapping code fence so the result is paste-ready.
    """
    text = _THINK_BLOCK.sub("", text).strip()
    if output_format == "inline":
        match = _OUTER_FENCE.match(text)
        if match:
            text = match.group(1)
    return text


def _display(language: Language) -> str:
    return "software" if language.key == "generic" else language.name
