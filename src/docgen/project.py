"""Document a whole project folder.

This is the shared core behind the ``docgen`` CLI and the
``/generate-project-docs`` API endpoint.
"""

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

from .cache import DocCache, content_hash
from .chunker import DEFAULT_MAX_CHARS, Chunk, chunk_source
from .config import Settings
from .files import DEFAULT_MAX_FILE_BYTES, find_source_files, iter_text
from .generator import generate_docs
from .languages import LANGUAGES, UnknownLanguageError, get_language

# Bump when the page layout or prompt changes so cached pages are regenerated.
PAGE_VERSION = "1"

# Turns (code, language, context) into Markdown. The CLI and API use the
# Ollama-backed one below; tests pass a fake.
DocFunction = Callable[[str, str, str], str]


def model_doc_function(settings: Settings) -> DocFunction:
    return lambda code, language, context: generate_docs(
        code, language, settings=settings, context=context or None
    )


def _is_unreachable(exc: BaseException) -> bool:
    """True when the error (or what caused it) means the server can't be reached."""
    while exc is not None:
        if isinstance(exc, (ConnectionError, httpx.TransportError)):
            return True
        exc = exc.__cause__
    return False


INDEX_FILE = "index.md"


@dataclass
class FileResult:
    path: str
    language: str
    doc: str  # path of the page, relative to the output folder
    status: str  # "generated", "unchanged", "planned", "failed", or "skipped"
    chunks: int = 0
    error: str | None = None


@dataclass
class ProjectReport:
    source: str
    output: str
    files: list[FileResult] = field(default_factory=list)
    error: str | None = None  # set when the run stopped early

    def count(self, status: str) -> int:
        return sum(1 for f in self.files if f.status == status)

    @property
    def generated(self) -> int:
        return self.count("generated")

    @property
    def unchanged(self) -> int:
        return self.count("unchanged")

    @property
    def failed(self) -> int:
        return self.count("failed")

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "output": self.output,
            "generated": self.generated,
            "unchanged": self.unchanged,
            "failed": self.failed,
            "error": self.error,
            "files": [asdict(f) for f in self.files],
        }


def parse_languages(lang: str | None) -> list[str] | None:
    """Turn ``--lang`` into a list of languages, or None for auto-detect."""
    if not lang or lang.strip().lower() == "auto":
        return None
    names = []
    for item in (x for x in lang.split(",") if x.strip()):
        try:
            names.append(get_language(item).key)
        except UnknownLanguageError as exc:
            supported = ", ".join(language.key for language in LANGUAGES)
            raise ValueError(
                f"Unknown language '{item.strip()}'. Supported: auto, {supported}"
            ) from exc
    return names


def doc_path_for(rel_path: str) -> str:
    """``src/app/main.py`` -> ``src/app/main.py.md`` (keeps same-named files apart)."""
    return rel_path + ".md"


def document_project(
    source: Path,
    output: Path,
    doc_fn: DocFunction,
    lang: str | None = "auto",
    exclude: Sequence[str] = (),
    max_chars: int = DEFAULT_MAX_CHARS,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    force: bool = False,
    dry_run: bool = False,
    cache_salt: str = "",
    on_progress: Callable[[FileResult], None] | None = None,
) -> ProjectReport:
    """Write one Markdown page per source file in ``source`` plus an index.

    Files whose content (and model settings, via ``cache_salt``) did not
    change since the last run are skipped unless ``force`` is set. With
    ``dry_run`` nothing is written and the model is not called.
    """
    source = Path(source).resolve()
    output = Path(output).resolve()
    if not source.is_dir():
        raise NotADirectoryError(f"Source folder not found: {source}")
    languages = parse_languages(lang)

    files = find_source_files(
        source,
        languages=languages,
        exclude=exclude,
        skip_dirs=[output],
        max_file_bytes=max_file_bytes,
    )
    cache = DocCache(output)
    report = ProjectReport(source=str(source), output=str(output))

    for f, text in iter_text(files):
        doc_rel = doc_path_for(f.rel_path)
        doc_abs = output / doc_rel
        if report.error:
            # The model is unreachable; keep any existing page and move on.
            report.files.append(FileResult(f.rel_path, f.language, doc_rel, "skipped"))
            continue
        digest = content_hash(text, PAGE_VERSION, str(max_chars), f.language, cache_salt)

        if not force and cache.is_fresh(f.rel_path, digest, doc_abs):
            result = FileResult(f.rel_path, f.language, doc_rel, "unchanged")
        else:
            chunks = chunk_source(text, f.language, max_chars)
            if dry_run:
                result = FileResult(f.rel_path, f.language, doc_rel, "planned", len(chunks))
            else:
                try:
                    page = render_page(f.rel_path, f.language, chunks, doc_fn, doc_rel)
                    doc_abs.parent.mkdir(parents=True, exist_ok=True)
                    doc_abs.write_text(page, encoding="utf-8")
                    cache.set(f.rel_path, digest, doc_rel)
                    result = FileResult(f.rel_path, f.language, doc_rel, "generated", len(chunks))
                except Exception as exc:  # one bad file should not stop the run
                    if _is_unreachable(exc):
                        # No point trying the other files against a server that is down.
                        report.error = str(exc)
                    result = FileResult(
                        f.rel_path, f.language, doc_rel, "failed", len(chunks), error=str(exc)
                    )

        report.files.append(result)
        if on_progress:
            on_progress(result)

    if not dry_run:
        _remove_stale_pages(cache, output, {f.rel_path for f in files})
        cache.save()
        write_index(output, source, report.files)

    return report


def render_page(
    rel_path: str, language: str, chunks: list[Chunk], doc_fn: DocFunction, doc_rel: str = ""
) -> str:
    up = "../" * doc_rel.count("/")
    lines = [
        f"# `{rel_path}`",
        "",
        f"_Language: {language} · [Back to index]({up}{INDEX_FILE})_",
        "",
    ]
    if len(chunks) <= 1:
        code = chunks[0].text if chunks else ""
        lines.append(doc_fn(code, language, "") if code.strip() else "_This file is empty._")
        return "\n".join(lines).rstrip() + "\n"

    for i, chunk in enumerate(chunks, 1):
        context = (
            f"This is part {i} of {len(chunks)} of the file `{rel_path}`, "
            f"covering {chunk.label}. Document only the code shown."
        )
        lines += [f"## {chunk.label}", "", doc_fn(chunk.text, language, context).strip(), ""]
    return "\n".join(lines).rstrip() + "\n"


def _remove_stale_pages(cache: DocCache, output: Path, current: Iterable[str]) -> None:
    """Delete pages this tool generated for source files that are gone."""
    current = set(current)
    for rel_path, entry in list(cache.entries.items()):
        if rel_path in current:
            continue
        page = output / entry.get("doc", doc_path_for(rel_path))
        try:
            if page.resolve().is_relative_to(output) and page.is_file():
                page.unlink()
        except OSError:
            pass
    cache.prune(current)


def write_index(output: Path, source: Path, results: list[FileResult]) -> None:
    by_dir = defaultdict(list)
    for r in results:
        if r.status in ("failed", "skipped") and not (output / r.doc).is_file():
            continue
        folder = r.path.rsplit("/", 1)[0] if "/" in r.path else "."
        by_dir[folder].append(r)

    lines = [f"# Documentation for `{source.name}`", ""]
    langs = sorted({r.language for r in results})
    lines.append(f"{len(results)} files · languages: {', '.join(langs) or 'none'}")
    lines.append("")
    for folder in sorted(by_dir):
        lines += [f"## `{folder}/`" if folder != "." else "## Project root", ""]
        for r in sorted(by_dir[folder], key=lambda r: r.path):
            name = r.path.rsplit("/", 1)[-1]
            lines.append(f"- [{name}]({r.doc}) · {r.language}")
        lines.append("")

    failed = [r for r in results if r.status == "failed"]
    skipped = [r for r in results if r.status == "skipped"]
    if failed:
        lines += ["## Not documented", ""]
        lines += [f"- `{r.path}`: {r.error}" for r in failed]
        lines.append("")
    if skipped:
        lines.append(f"{len(skipped)} more files were skipped because the model was unreachable.")
        lines.append("")

    output.mkdir(parents=True, exist_ok=True)
    (output / INDEX_FILE).write_text("\n".join(lines), encoding="utf-8")
