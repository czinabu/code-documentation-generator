"""Find the source files in a project folder."""

import fnmatch
import os
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from .languages import from_filename

# Folders that never hold code worth documenting.
DEFAULT_IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "venv",
    ".venv",
    "env",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    "dist",
    "build",
    "target",
    "out",
    "bin",
    "obj",
    ".idea",
    ".vscode",
    "vendor",
    ".next",
}

# Files bigger than this are almost always generated or minified.
DEFAULT_MAX_FILE_BYTES = 512 * 1024


@dataclass(frozen=True)
class SourceFile:
    path: Path  # absolute path on disk
    rel_path: str  # path relative to the project root, with forward slashes
    language: str


def _matches(rel_path: str, patterns: Sequence[str]) -> bool:
    name = rel_path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(rel_path, p) or fnmatch.fnmatch(name, p) for p in patterns)


def find_source_files(
    root: Path,
    languages: Iterable[str] | None = None,
    exclude: Sequence[str] = (),
    skip_dirs: Iterable[Path] = (),
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> list[SourceFile]:
    """Walk ``root`` and return the source files to document, sorted by path.

    ``languages`` limits the result to those languages; None means any
    language we recognise. ``exclude`` holds glob patterns matched against
    the relative path and the file name. ``skip_dirs`` are absolute folders
    to leave out, such as the output folder when it sits inside ``root``.
    """
    root = Path(root).resolve()
    wanted = set(languages) if languages else None
    skip = {Path(d).resolve() for d in skip_dirs}
    found: list[SourceFile] = []

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = sorted(
            d
            for d in dirnames
            if d not in DEFAULT_IGNORED_DIRS
            and not d.startswith(".")
            and (current / d).resolve() not in skip
            and not _matches(_rel(root, current / d), exclude)
        )
        for name in sorted(filenames):
            path = current / name
            lang = from_filename(name)
            language = lang.key if lang else None
            if language is None or (wanted is not None and language not in wanted):
                continue
            rel = _rel(root, path)
            if _matches(rel, exclude):
                continue
            try:
                if path.stat().st_size > max_file_bytes or not path.is_file():
                    continue
            except OSError:
                continue
            found.append(SourceFile(path=path, rel_path=rel, language=language))

    return sorted(found, key=lambda f: f.rel_path)


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def iter_text(files: Iterable[SourceFile]) -> Iterator[tuple]:
    """Yield ``(file, text)`` pairs, skipping files that are not UTF-8 text."""
    for f in files:
        try:
            text = f.path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "\x00" in text:
            continue
        yield f, text
