# Local AI Code Documentation Generator

A small FastAPI service that turns code snippets into clean Markdown documentation using a model running on your own [Ollama](https://ollama.com) server (default: `qwen3:14b`). Nothing leaves your machine or network.

## Features

- `docgen src/ --out docs/` documents a whole project: one Markdown page per file plus an index
- Splits large files at functions and classes to fit the model's context, and skips unchanged files on reruns
- `POST /generate-docs` returns docs for a code snippet, in that language's native style
- Detects the language from a `language` field, the `filename` extension, or the code itself
- Two output formats: a Markdown reference summary, or your code with paste-ready doc comments
  (Python docstrings, JSDoc, TSDoc, Javadoc, KDoc, Go doc comments, rustdoc `///`, C# XML docs,
  Doxygen for C/C++, YARD, PHPDoc)
- Works with any Ollama chat model, local or remote (e.g. over Tailscale)
- Configured with environment variables or a TOML file, no code edits needed
- Reuses one Ollama connection, logs each request, and returns clear errors when Ollama is down
- Strips `<think>` blocks that reasoning models such as qwen3 emit
- Usable as a library: `from docgen import generate_docs`

## Requirements

- Python 3.11+
- An Ollama server with a model pulled, for example:

```bash
ollama pull qwen3:14b
```

## Install

```bash
git clone https://github.com/czinabu/code-documentation-generator.git
cd code-documentation-generator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # pinned versions
pip install -e .                  # installs the docgen package
```

## Run

From the repository root:

```bash
python -m docgen                  # http://127.0.0.1:8000
python -m docgen --host 0.0.0.0 --port 8000 --reload
```

`docgen-server` (installed by `pip install -e .`) does the same thing. Interactive API docs are at `http://127.0.0.1:8000/docs`.

## Use

```bash
curl -s http://127.0.0.1:8000/generate-docs \
  -H 'Content-Type: application/json' \
  -d '{"code": "def add(a, b):\n    return a + b"}'
```

```json
{
  "documentation": "# add\n\nAdds two numbers...",
  "language": "python",
  "language_source": "content",
  "output_format": "markdown"
}
```

Optional request fields:

| Field | Values | Default | Purpose |
| --- | --- | --- | --- |
| `language` | `python`, `javascript`, `typescript`, `java`, `kotlin`, `go`, `rust`, `csharp`, `cpp`, `c`, `ruby`, `php` (aliases like `ts`, `golang`, `c#` work) | detected | Forces the language |
| `filename` | e.g. `"handlers.go"` | none | Detects the language from the extension |
| `output_format` | `markdown` or `inline` | `markdown` | `inline` returns your code with native doc comments added, ready to paste back |

Detection order is `language`, then `filename`, then a quick look at the code; `language_source` in the response says which one was used (`request`, `filename`, `content` or `fallback`). For example:

```bash
curl -s http://127.0.0.1:8000/generate-docs \
  -H 'Content-Type: application/json' \
  -d '{"code": "func Add(a, b int) int {\n\treturn a + b\n}", "filename": "math.go", "output_format": "inline"}'
```

```json
{
  "documentation": "// Add returns the sum of a and b.\nfunc Add(a, b int) int {\n\treturn a + b\n}",
  "language": "go",
  "language_source": "filename",
  "output_format": "inline"
}
```

| Status | Meaning |
| --- | --- |
| 200 | Documentation generated |
| 400 | `code` was empty, or `language` is not supported |
| 422 | Body was not JSON, had no `code` field, or `output_format` was invalid |
| 502 | Ollama was unreachable, timed out, or returned an error (e.g. model not pulled) |

`GET /` returns a status message and the configured model. `GET /languages` lists every supported language with its extensions and doc comment style.

From Python:

```python
from docgen import generate_docs

print(generate_docs("def add(a, b):\n    return a + b", language="python"))
print(generate_docs(open("server.go").read(), filename="server.go", output_format="inline"))

# generate() also reports which language was used and how it was found.
from docgen import generate

result = generate("fn main() {}")
print(result.language.key, result.language_source)  # rust content
```

## Document a whole project

```bash
docgen src/ --out docs/
```

This walks `src/`, documents every source file it recognises, and writes `docs/<path>.md` for each one plus `docs/index.md` linking them all, grouped by folder.

| Option | What it does |
| --- | --- |
| `--lang auto` | Default. Documents every supported language (see `GET /languages`), detected by file extension. Pass `--lang python,go` to limit it. |
| `--out DIR` | Where pages go (default `docs`). It is never documented itself, even inside the source folder. |
| `--exclude GLOB` | Skip matching files or folders, e.g. `-x "tests/*"`. Repeatable. |
| `--max-chars N` | Largest piece sent to the model at once (default 12000). Bigger files are split at top-level functions and classes, and the page gets one section per part. |
| `--force` | Regenerate every page. Without it, files whose content, model and settings are unchanged are skipped, using hashes in `docs/.docgen-cache.json`. |
| `--dry-run` | List what would be documented without calling the model. |
| `--model`, `--host` | Override the configured model and Ollama server for this run. |
| `--json`, `--quiet` | Machine-readable summary, or summary only. |

`.git`, `node_modules`, virtualenvs, build output, hidden folders and files over 512 KB are always skipped. Pages for deleted source files are removed. If Ollama can't be reached the run stops after the first file; run it again to pick up where it left off. The exit code is 0 on success, 1 if any file failed, 2 for bad arguments.

The API runs the same code at `POST /generate-project-docs`:

```bash
curl -s http://127.0.0.1:8000/generate-project-docs \
  -H 'Content-Type: application/json' \
  -d '{"source": "/path/to/project/src", "out": "/path/to/project/docs"}'
```

It returns a per-file report (`generated`, `unchanged`, `failed`, and a `files` list). Paths are on the machine running the API, which can read and write anywhere that user can, so keep the server bound to localhost or a network you trust.

## Configuration

Settings come from defaults, then an optional TOML file, then environment variables (later wins).

| Setting | Environment variable | Default |
| --- | --- | --- |
| `model` | `DOCGEN_MODEL` | `qwen3:14b` |
| `ollama_host` | `DOCGEN_OLLAMA_HOST`, falling back to `OLLAMA_HOST` | `http://localhost:11434` |
| `timeout` (seconds) | `DOCGEN_TIMEOUT` | `120` |
| `log_level` | `DOCGEN_LOG_LEVEL` | `INFO` |

For example, to use a remote Ollama server over Tailscale:

```bash
DOCGEN_OLLAMA_HOST=http://100.x.y.z:11434 DOCGEN_MODEL=qwen2.5-coder:14b python -m docgen
```

To use a file instead, copy `docgen.example.toml` to `docgen.toml` in the directory you run from, or point `DOCGEN_CONFIG` at any TOML file.

## Project layout

```
src/docgen/
  api.py             FastAPI app (create_app factory)
  config.py          Settings: defaults, TOML file, env vars
  client.py          Shared Ollama client
  languages.py       Supported languages, doc styles and language detection
  prompts.py         Per-language prompts and output cleanup
  generator.py       generate() / generate_docs(): the model call, independent of the API
  cli.py             `docgen` command for whole projects
  project.py         document_project(): shared by the CLI and the API
  files.py           Finds source files, skipping vendored and build folders
  chunker.py         Splits large files at functions and classes
  cache.py           Content-hash cache so unchanged files are skipped
  logging_config.py  Logging setup
  __main__.py        `python -m docgen` server entry point
tests/               pytest suite; Ollama is faked, no server needed
```

## Development

```bash
pip install -r requirements-dev.txt && pip install -e .
pytest
ruff check . && ruff format --check .
```

## License

MIT. See [LICENSE](LICENSE).
