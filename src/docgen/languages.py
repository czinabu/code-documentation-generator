"""Language registry and detection.

Each supported language describes its native documentation convention so the
prompt builder can ask the model for output that drops straight into a codebase.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePath


@dataclass(frozen=True)
class Language:
    key: str
    name: str
    extensions: tuple[str, ...]
    doc_style: str
    style_rules: str
    aliases: tuple[str, ...] = field(default_factory=tuple)


GENERIC = Language(
    key="generic",
    name="Unknown language",
    extensions=(),
    doc_style="the conventional documentation comment style for the language",
    style_rules=(
        "- Identify the language from the code and use its idiomatic doc comment syntax.\n"
        "- Describe purpose, parameters, return values and errors."
    ),
)

LANGUAGES: tuple[Language, ...] = (
    Language(
        key="python",
        name="Python",
        extensions=(".py", ".pyi", ".pyw"),
        aliases=("py", "python3"),
        doc_style="PEP 257 docstrings in Google style",
        style_rules=(
            '- Use triple-quoted docstrings (""") as the first statement of each module, class '
            "and function.\n"
            "- One-line summary, blank line, then details.\n"
            "- Use Google-style sections: Args:, Returns:, Yields:, Raises:, Example:.\n"
            "- Do not repeat type hints that are already in the signature unless they add meaning."
        ),
    ),
    Language(
        key="javascript",
        name="JavaScript",
        extensions=(".js", ".mjs", ".cjs", ".jsx"),
        aliases=("js", "node", "jsx"),
        doc_style="JSDoc block comments",
        style_rules=(
            "- Use /** ... */ blocks placed directly above each function, class and exported "
            "constant.\n"
            "- Use @param {Type} name - description, @returns {Type} description, @throws {Type} "
            "description.\n"
            "- Add @example where a short example helps; use @async / @class where relevant."
        ),
    ),
    Language(
        key="typescript",
        name="TypeScript",
        extensions=(".ts", ".tsx", ".mts", ".cts"),
        aliases=("ts", "tsx"),
        doc_style="TSDoc block comments",
        style_rules=(
            "- Use /** ... */ blocks placed directly above each declaration.\n"
            "- Use @param name - description, @returns description, @throws description, "
            "@example.\n"
            "- Do not put types in braces; TypeScript already carries the types."
        ),
    ),
    Language(
        key="java",
        name="Java",
        extensions=(".java",),
        doc_style="Javadoc comments",
        style_rules=(
            "- Use /** ... */ blocks above each class, constructor, method and public field.\n"
            "- First sentence is the summary. Use <p> for further paragraphs.\n"
            "- Use @param, @return, @throws, and {@code ...} / {@link ...} for inline references."
        ),
    ),
    Language(
        key="kotlin",
        name="Kotlin",
        extensions=(".kt", ".kts"),
        aliases=("kt",),
        doc_style="KDoc comments",
        style_rules=(
            "- Use /** ... */ blocks above each declaration, written in Markdown.\n"
            "- Use @param, @return, @throws, @property, and [name] links to other symbols."
        ),
    ),
    Language(
        key="go",
        name="Go",
        extensions=(".go",),
        aliases=("golang",),
        doc_style="Go doc comments",
        style_rules=(
            "- Use // line comments placed directly above each package clause and exported "
            "declaration.\n"
            '- Each comment starts with the name of the thing it documents (e.g. "// Add returns '
            '...").\n'
            "- Write complete sentences. Do not use @param style tags; describe parameters in "
            "prose.\n"
            "- Use [Name] links and indented blocks for code, per Go 1.19 doc comment syntax."
        ),
    ),
    Language(
        key="rust",
        name="Rust",
        extensions=(".rs",),
        aliases=("rs",),
        doc_style="rustdoc /// comments",
        style_rules=(
            "- Use /// outer doc comments above items and //! for module or crate docs.\n"
            "- Write in Markdown. Start with a one-line summary.\n"
            "- Use the conventional headings: # Arguments, # Returns, # Errors, # Panics, # "
            "Safety, # Examples.\n"
            "- Put examples in ``` fenced blocks so they work as doctests."
        ),
    ),
    Language(
        key="csharp",
        name="C#",
        extensions=(".cs",),
        aliases=("c#", "cs", "dotnet"),
        doc_style="XML documentation comments",
        style_rules=(
            "- Use /// lines with XML tags above each type and member.\n"
            '- Use <summary>, <param name="...">, <returns>, <exception cref="...">, <example>.'
        ),
    ),
    Language(
        key="cpp",
        name="C++",
        extensions=(".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"),
        aliases=("c++", "cxx"),
        doc_style="Doxygen comments",
        style_rules=(
            "- Use /** ... */ blocks (or ///) above each declaration.\n"
            "- Use @brief, @param, @tparam, @return, @throws, @note."
        ),
    ),
    Language(
        key="c",
        name="C",
        extensions=(".c", ".h"),
        doc_style="Doxygen comments",
        style_rules=(
            "- Use /** ... */ blocks above each function, struct and macro.\n"
            "- Use @brief, @param[in]/@param[out], @return, @note. Mention ownership and NULL "
            "handling."
        ),
    ),
    Language(
        key="ruby",
        name="Ruby",
        extensions=(".rb",),
        aliases=("rb",),
        doc_style="YARD comments",
        style_rules=(
            "- Use # line comments directly above each method, class and module.\n"
            "- Use YARD tags: @param name [Type] description, @return [Type] description, @raise "
            "[Error], @example."
        ),
    ),
    Language(
        key="php",
        name="PHP",
        extensions=(".php",),
        doc_style="PHPDoc blocks",
        style_rules=(
            "- Use /** ... */ blocks above each class, method, function and property.\n"
            "- Use @param Type $name description, @return Type description, @throws Type."
        ),
    ),
)

_BY_KEY: dict[str, Language] = {}
_BY_EXTENSION: dict[str, Language] = {}
for _lang in LANGUAGES:
    for _name in (_lang.key, _lang.name.lower(), *_lang.aliases):
        _BY_KEY[_name] = _lang
    for _ext in _lang.extensions:
        _BY_EXTENSION[_ext] = _lang


class UnknownLanguageError(ValueError):
    """Raised when an explicitly requested language is not supported."""


def get_language(name: str) -> Language:
    """Look up a language by key, display name or alias (case-insensitive)."""
    lang = _BY_KEY.get(name.strip().lower())
    if lang is None:
        supported = ", ".join(item.key for item in LANGUAGES)
        raise UnknownLanguageError(f"Unsupported language '{name}'. Supported: {supported}.")
    return lang


def from_filename(filename: str) -> Language | None:
    """Return the language for a filename's extension, or None if unknown."""
    suffix = PurePath(filename).suffix.lower()
    return _BY_EXTENSION.get(suffix)


# Ordered content heuristics, used only when no language or filename is given.
# Each pattern is a strong, cheap signal; the first match wins.
_SHEBANGS = (
    (re.compile(r"^#!.*\bpython"), "python"),
    (re.compile(r"^#!.*\bnode"), "javascript"),
    (re.compile(r"^#!.*\bruby"), "ruby"),
    (re.compile(r"^#!.*\bphp"), "php"),
)
_HEURISTIC_SOURCES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("php", (r"<\?php",)),
    ("go", (r"^\s*package\s+\w+\s*$", r"^\s*func\s+(\(\w+\s+\*?\w+\)\s*)?\w+\s*\(")),
    ("rust", (r"^\s*(pub(\(crate\))?\s+)?fn\s+\w+", r"^\s*impl\b", r"^\s*use\s+\w+::")),
    (
        "java",
        (
            r"^\s*(public|private|protected)\s+(static\s+)?(final\s+)?[\w<>\[\]]+\s+\w+"
            r"\s*\(.*\)\s*(throws\s+[\w, ]+)?\s*\{",
        ),
    ),
    ("csharp", (r"^\s*using\s+System", r"^\s*namespace\s+[\w.]+\s*[{;]")),
    ("kotlin", (r"^\s*(data\s+class|fun)\s+\w+",)),
    ("cpp", (r"^\s*#include\s*<(iostream|vector|string|memory|map)>", r"std::", r"\btemplate\s*<")),
    ("c", (r"^\s*#include\s*[<\"]",)),
    ("typescript", (r"^\s*(interface|type)\s+\w+\s*[={<]", r":\s*(string|number|boolean)\b")),
    (
        "python",
        (
            r"^\s*(async\s+)?def\s+\w+\s*\(.*\)\s*(->\s*[^:]+)?:",
            r"^\s*class\s+\w+(\(.*\))?:\s*$",
            r"^\s*(from\s+\w[\w.]*\s+)?import\s+\w",
        ),
    ),
    ("ruby", (r"^\s*def\s+\w+[?!]?(\(.*\))?\s*$", r"^\s*end\s*$")),
    (
        "javascript",
        (r"\bfunction\b", r"=>", r"\bconst\s+\w+\s*=", r"\bmodule\.exports\b", r"\brequire\("),
    ),
)
_HEURISTICS = tuple(
    (re.compile("|".join(patterns), re.M), key) for key, patterns in _HEURISTIC_SOURCES
)


def guess_from_code(code: str) -> Language | None:
    """Best-effort guess from source text. Returns None when nothing matches."""
    first_line = code.lstrip().splitlines()[0] if code.strip() else ""
    for pattern, key in _SHEBANGS:
        if pattern.search(first_line):
            return _BY_KEY[key]
    for pattern, key in _HEURISTICS:
        if pattern.search(code):
            return _BY_KEY[key]
    return None


def detect_language(
    code: str,
    language: str | None = None,
    filename: str | None = None,
) -> tuple[Language, str]:
    """Resolve the language for a request.

    Precedence: explicit ``language`` field, then ``filename`` extension, then
    content heuristics, then the generic fallback.

    Returns:
        A ``(Language, source)`` pair, where ``source`` is one of
        ``"request"``, ``"filename"``, ``"content"`` or ``"fallback"``.

    Raises:
        UnknownLanguageError: If ``language`` is given but not supported.
    """
    if language and language.strip():
        return get_language(language), "request"
    if filename:
        lang = from_filename(filename)
        if lang is not None:
            return lang, "filename"
    lang = guess_from_code(code)
    if lang is not None:
        return lang, "content"
    return GENERIC, "fallback"
