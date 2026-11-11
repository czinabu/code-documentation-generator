"""Prompt construction for documentation generation."""

from __future__ import annotations

SYSTEM_PROMPT = (
    "You are an expert technical documentation writer. "
    "Generate clean, professional, and well-structured Markdown documentation "
    "for the given code snippet.\n\n"
    "Rules:\n"
    "- Use proper Markdown with headings (#, ##, ###)\n"
    "- Start with a brief overview\n"
    "- Include Parameters and Returns sections when applicable\n"
    "- Add a short usage example\n"
    "- Keep it concise and readable\n"
    "- Do not add extra explanations or fluff"
)


def build_messages(code: str, language: str | None = None) -> list[dict[str, str]]:
    """Return the chat messages sent to the model for ``code``."""
    user_content = code
    if language:
        user_content = f"Language: {language}\n\n```{language.lower()}\n{code}\n```"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
