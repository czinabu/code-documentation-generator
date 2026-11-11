"""Command line entry point: ``docgen SOURCE --out DOCS``.

Examples::

    docgen src/ --out docs/
    docgen . --lang python,typescript --exclude "tests/*" --out docs/
    docgen src/ --dry-run
"""

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from .chunker import DEFAULT_MAX_CHARS
from .config import ConfigError, Settings
from .files import DEFAULT_MAX_FILE_BYTES
from .languages import LANGUAGES
from .project import FileResult, document_project, model_doc_function

_MARK = {"generated": "+", "unchanged": "=", "planned": "?", "failed": "!", "skipped": "-"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="docgen",
        description="Generate Markdown documentation for every source file in a folder "
        "using a local Ollama model.",
    )
    p.add_argument("source", type=Path, help="folder to document")
    p.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("docs"),
        help="folder to write the Markdown pages to (default: docs)",
    )
    p.add_argument(
        "-l",
        "--lang",
        default="auto",
        help="'auto' to document every recognised language, or a comma-separated "
        f"list to limit it. Supported: {', '.join(lang.key for lang in LANGUAGES)}",
    )
    p.add_argument(
        "-x",
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="skip files or folders matching this pattern (repeatable)",
    )
    p.add_argument("--model", help="Ollama model (default: from settings, qwen3:14b)")
    p.add_argument("--host", help="Ollama server URL (default: from settings, localhost)")
    p.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help="largest piece of code sent to the model at once; bigger files are "
        f"split into functions and classes (default: {DEFAULT_MAX_CHARS})",
    )
    p.add_argument(
        "--max-file-kb",
        type=int,
        default=DEFAULT_MAX_FILE_BYTES // 1024,
        help="skip files larger than this, usually generated code "
        f"(default: {DEFAULT_MAX_FILE_BYTES // 1024})",
    )
    p.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="regenerate every page even if the source did not change",
    )
    p.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="list what would be documented without calling the model",
    )
    p.add_argument("--json", action="store_true", help="print the summary as JSON")
    p.add_argument("-q", "--quiet", action="store_true", help="only print the summary")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        settings = Settings.load()
        overrides = {"model": args.model, "ollama_host": args.host}
        settings = dataclasses.replace(settings, **{k: v for k, v in overrides.items() if v})
    except ConfigError as exc:
        print(f"docgen: config error: {exc}", file=sys.stderr)
        return 2

    def progress(r: FileResult) -> None:
        if args.quiet or args.json:
            return
        extra = f" ({r.chunks} parts)" if r.chunks > 1 else ""
        err = f": {r.error}" if r.error else ""
        if r.status == "skipped":
            return
        print(
            f"  {_MARK.get(r.status, ' ')} {r.path} [{r.language}] {r.status}{extra}{err}",
            flush=True,
        )

    try:
        report = document_project(
            args.source,
            args.out,
            doc_fn=model_doc_function(settings),
            lang=args.lang,
            exclude=args.exclude,
            max_chars=args.max_chars,
            max_file_bytes=args.max_file_kb * 1024,
            force=args.force,
            dry_run=args.dry_run,
            cache_salt=settings.model,
            on_progress=progress,
        )
    except (ValueError, NotADirectoryError) as exc:
        print(f"docgen: error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    elif args.dry_run:
        print(
            f"Dry run: {report.count('planned')} to generate, "
            f"{report.unchanged} unchanged. Nothing written."
        )
    elif report.error:
        print(f"docgen: stopped: {report.error}", file=sys.stderr)
        print(
            f"{report.generated} generated before stopping, "
            f"{report.count('skipped')} skipped. Run again to continue.",
            file=sys.stderr,
        )
    else:
        print(
            f"Done: {report.generated} generated, {report.unchanged} unchanged, "
            f"{report.failed} failed. Index: {Path(report.output) / 'index.md'}"
        )
    return 1 if report.failed or report.error else 0


if __name__ == "__main__":
    sys.exit(main())
