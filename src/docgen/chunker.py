"""Split source files into pieces that fit in the model's context.

A file that fits within the budget is sent whole. A bigger file is cut at
top-level declarations (functions, classes, types), and neighbouring small
pieces are packed back together so we make as few model calls as possible.
A single declaration that is still too big is cut into line windows.

Python uses the ``ast`` module for exact boundaries. Other languages use a
per-language regex for lines that start a top-level declaration, which is
good enough to find sensible cut points without a parser per language.
"""

import ast
import re
from dataclasses import dataclass

# Roughly 4 characters per token; 12k chars leaves room for the prompt and
# the answer in an 8k-token context window.
DEFAULT_MAX_CHARS = 12_000


@dataclass
class Chunk:
    text: str
    start_line: int  # 1-based, inclusive
    end_line: int  # 1-based, inclusive
    names: list[str]

    @property
    def label(self) -> str:
        span = f"lines {self.start_line}-{self.end_line}"
        if self.names:
            return f"{', '.join(self.names)} ({span})"
        return span


_C_LIKE_DECL = (
    r"(?:(?:public|private|protected|internal|static|final|abstract|sealed|"
    r"partial|async|override|virtual|inline|extern|const|unsafe|export|default|"
    r"open|data|suspend)\s+)*"
)

# Each pattern matches a line that begins a top-level declaration and
# captures its name. Patterns are anchored at column 0 so nested members do
# not cause cuts.
DECL_PATTERNS = {
    "javascript": [
        r"^(?:export\s+(?:default\s+)?)?(?:async\s+)?function\*?\s+(\w+)",
        r"^(?:export\s+(?:default\s+)?)?class\s+(\w+)",
        r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=",
    ],
    "go": [
        r"^func\s+(?:\([^)]*\)\s*)?(\w+)",
        r"^type\s+(\w+)",
    ],
    "rust": [
        r"^(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+(\w+)",
        r"^(?:pub(?:\([^)]*\))?\s+)?(?:struct|enum|trait|mod|type)\s+(\w+)",
        r"^impl(?:<[^>]*>)?\s+(?:[\w:<>, ]+\s+for\s+)?([\w:]+)",
    ],
    "java": [
        r"^" + _C_LIKE_DECL + r"(?:class|interface|enum|record|@interface)\s+(\w+)",
    ],
    "ruby": [
        r"^(?:class|module)\s+([\w:]+)",
        r"^def\s+(?:self\.)?(\w+[?!=]?)",
    ],
    "php": [
        r"^" + _C_LIKE_DECL + r"(?:class|interface|trait|enum)\s+(\w+)",
        r"^function\s+(\w+)",
    ],
    "swift": [
        r"^" + _C_LIKE_DECL + r"(?:class|struct|enum|protocol|extension|func)\s+(\w+)",
    ],
    "c": [
        # A function definition: a type then a name then an argument list,
        # starting at column 0 and not ending in ';'.
        r"^(?!return\b|if\b|else\b|for\b|while\b|switch\b|typedef\b)"
        r"[A-Za-z_][\w\s\*&:<>,]*?\b(\w+)\s*\([^;]*$",
        r"^(?:typedef\s+)?(?:struct|union|enum|class|namespace)\s+(\w+)",
    ],
    "shell": [
        r"^(?:function\s+)?(\w+)\s*\(\)\s*\{?",
    ],
    "lua": [
        r"^(?:local\s+)?function\s+([\w.:]+)",
    ],
}
DECL_PATTERNS["typescript"] = DECL_PATTERNS["javascript"] + [
    r"^(?:export\s+)?(?:declare\s+)?(?:interface|type|enum|namespace)\s+(\w+)",
    r"^(?:export\s+)?(?:abstract\s+)?class\s+(\w+)",
]
DECL_PATTERNS["kotlin"] = [
    r"^" + _C_LIKE_DECL + r"(?:class|interface|object|enum\s+class|fun)\s+(?:<[^>]*>\s*)?([\w.]+)",
]
DECL_PATTERNS["scala"] = [
    r"^(?:case\s+)?(?:class|object|trait|def)\s+(\w+)",
]
DECL_PATTERNS["csharp"] = DECL_PATTERNS["java"] + [
    r"^namespace\s+([\w.]+)",
    r"^" + _C_LIKE_DECL + r"struct\s+(\w+)",
]
DECL_PATTERNS["cpp"] = DECL_PATTERNS["c"]
DECL_PATTERNS["dart"] = [
    r"^(?:abstract\s+)?(?:class|mixin|extension|enum)\s+(\w+)",
]

_COMPILED = {lang: [re.compile(p) for p in patterns] for lang, patterns in DECL_PATTERNS.items()}

# Lines that belong with the declaration below them.
_LEADING = re.compile(r"^\s*(?:#|//|/\*|\*|\*/|@|\[|--|///)")


def chunk_source(text: str, language: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[Chunk]:
    """Split ``text`` into chunks of at most ``max_chars`` characters each."""
    lines = text.splitlines(keepends=True)
    if not lines:
        return []
    if len(text) <= max_chars:
        return [Chunk(text=text, start_line=1, end_line=len(lines), names=[])]

    segments = _segments(lines, language)
    return _pack(lines, segments, max_chars)


def _segments(lines: list[str], language: str) -> list[tuple[int, int, str | None]]:
    """Return ``(start, end, name)`` spans (0-based, end exclusive) that cover the file."""
    starts: list[tuple[int, str | None]] = []
    if language == "python":
        starts = _python_starts(lines)
    else:
        patterns = _COMPILED.get(language, [])
        for i, line in enumerate(lines):
            for pat in patterns:
                m = pat.match(line)
                if m:
                    starts.append((_pull_back(lines, i), m.group(1)))
                    break

    # Everything before the first declaration (imports, constants) is its own
    # unnamed segment. Keep the first match when two share a start line.
    unique: list[tuple[int, str | None]] = []
    for start, name in sorted([(0, None)] + starts, key=lambda s: (s[0], s[1] is None)):
        if not unique or unique[-1][0] != start:
            unique.append((start, name))

    spans = []
    for idx, (start, name) in enumerate(unique):
        end = unique[idx + 1][0] if idx + 1 < len(unique) else len(lines)
        if end > start:
            spans.append((start, end, name))
    return spans


def _python_starts(lines: list[str]) -> list[tuple[int, str | None]]:
    try:
        tree = ast.parse("".join(lines))
    except SyntaxError:
        # Fall back to a column-0 regex if the file does not parse.
        pat = re.compile(r"^(?:async\s+)?(?:def|class)\s+(\w+)")
        return [
            (_pull_back(lines, i), m.group(1))
            for i, line in enumerate(lines)
            if (m := pat.match(line))
        ]
    starts = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
            starts.append((_pull_back(lines, first), node.name))
    return starts


def _pull_back(lines: list[str], i: int) -> int:
    """Move a declaration start up to include the comments and attributes above it."""
    while i > 0 and lines[i - 1].strip() and _LEADING.match(lines[i - 1]):
        i -= 1
    return i


def _pack(lines: list[str], spans, max_chars: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    cur_start = None
    cur_end = 0
    cur_names: list[str] = []
    cur_size = 0

    def flush():
        nonlocal cur_start, cur_names, cur_size
        if cur_start is not None:
            text = "".join(lines[cur_start:cur_end])
            if text.strip():
                chunks.append(Chunk(text, cur_start + 1, cur_end, cur_names))
        cur_start, cur_names, cur_size = None, [], 0

    for start, end, name in spans:
        size = sum(len(line) for line in lines[start:end])
        if size > max_chars:
            flush()
            chunks.extend(_split_lines(lines, start, end, name, max_chars))
            continue
        if cur_start is not None and cur_size + size > max_chars:
            flush()
        if cur_start is None:
            cur_start = start
        cur_end = end
        cur_size += size
        if name:
            cur_names.append(name)
    flush()
    return chunks


def _split_lines(lines, start, end, name, max_chars) -> list[Chunk]:
    """Cut an oversized span into windows, preferring blank lines as cut points."""
    out: list[Chunk] = []
    i = start
    part = 1
    while i < end:
        size = 0
        j = i
        last_blank = None
        while j < end and size + len(lines[j]) <= max_chars:
            size += len(lines[j])
            if not lines[j].strip():
                last_blank = j
            j += 1
        if j == i:  # one line longer than the budget: take it alone, truncated
            j = i + 1
        elif j < end and last_blank is not None and last_blank > i + (j - i) // 2:
            j = last_blank + 1
        text = "".join(lines[i:j])
        if len(text) > max_chars:
            text = text[:max_chars]
        names = [f"{name} (part {part})"] if name else []
        if text.strip():
            out.append(Chunk(text, i + 1, j, names))
        part += 1
        i = j
    return out
