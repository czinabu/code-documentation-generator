# Local AI Code Documentation Generator

A small FastAPI service that turns code snippets into clean Markdown documentation using a model running on your own [Ollama](https://ollama.com) server (default: `qwen3:14b`). Nothing leaves your machine or network.

## Features

- `POST /generate-docs` returns Markdown docs for a code snippet
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
{"documentation": "# add\n\nAdds two numbers..."}
```

| Status | Meaning |
| --- | --- |
| 200 | Documentation generated |
| 400 | `code` was empty |
| 422 | Body was not JSON or had no `code` field |
| 502 | Ollama was unreachable, timed out, or returned an error (e.g. model not pulled) |

`GET /` returns a status message and the configured model.

From Python:

```python
from docgen import generate_docs

print(generate_docs("def add(a, b):\n    return a + b", language="python"))
```

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
  prompts.py         System prompt and message construction
  generator.py       generate_docs(): the model call, independent of the API
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
