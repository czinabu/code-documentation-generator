# FastAPI + Ollama + Qwen Documentation Generator

This is a FastAPI application that uses the Ollama Python client to generate documentation for code snippets using the Qwen model.

## Features
- Accepts a code snippet via a POST request
- Uses the Qwen model from Ollama to generate documentation
- Language-aware: detects the language from a `language` field, the `filename` extension, or the code itself
- Two output formats: a Markdown reference summary, or the original code with paste-ready native doc comments
  (Python docstrings, JSDoc, TSDoc, Javadoc, KDoc, Go doc comments, rustdoc `///`, C# XML docs, Doxygen, YARD, PHPDoc)
- Configurable Ollama host (e.g., for remote or Tailscale setups)
- Includes a root endpoint (`/`) to show the current model and status

## Requirements

- Python 3.8 or higher
- Ollama server running locally or remotely (e.g., via Tailscale)
- The Qwen model running in Ollama

## How to Run

### 1. Install Ollama and Run the Qwen Model

Make sure you have [Ollama installed](https://ollama.com) and the Qwen model running:

```bash
ollama run qwen3:14b
```

If you're using a remote Ollama server (e.g., via Tailscale), you can set the `OLLAMA_HOST` in your `main.py` file accordingly.

### 2. Install Dependencies

Install the required Python packages:

```bash
pip install fastapi uvicorn ollama
```

### 3. Run the App

Start the FastAPI application:

```bash
uvicorn main:app --reload
```

The app will be available at `http://localhost:8000`.

### 4. Send a POST Request

You can send a POST request to the `/generate-docs` endpoint with a JSON body like this:

```json
{
  "code": "def add(a, b):\n    return a + b"
}
```

> ⚠️ **Important:** Your request must be in **JSON format**, and it must include a `"code"` field with the code snippet as its value.

Optional fields:

| Field | Values | Default | Purpose |
|---|---|---|---|
| `language` | `python`, `javascript`, `typescript`, `java`, `kotlin`, `go`, `rust`, `csharp`, `cpp`, `c`, `ruby`, `php` (aliases like `ts`, `golang`, `c#` work) | detected | Forces the language |
| `filename` | e.g. `"handlers.go"` | none | Detects the language from the extension |
| `output_format` | `markdown` or `inline` | `markdown` | `inline` returns your code with native doc comments added, ready to paste back |

Detection order is `language`, then `filename`, then a quick look at the code. Example:

```json
{
  "code": "func Add(a, b int) int {\n\treturn a + b\n}",
  "filename": "math.go",
  "output_format": "inline"
}
```

The response includes the detected language and how it was found:

```json
{
  "documentation": "// Add returns the sum of a and b.\nfunc Add(a, b int) int {\n\treturn a + b\n}",
  "language": "go",
  "language_source": "filename",
  "output_format": "inline"
}
```

`GET /languages` lists every supported language with its extensions and doc comment style.

### 5. Access the Root Endpoint

You can access the root endpoint at `http://localhost:8000` to see a simple status message and the current model being used.

---

## Configuration

You can customize the following in your `main.py` file:

- `MODEL_NAME`: Change this to use a different model (e.g., `"qwen2.5:14b"`).
- `OLLAMA_HOST`: Update this if you're connecting to a remote Ollama server (e.g., via Tailscale).

---

## Running Tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Tests mock the Ollama client, so no model server is needed.

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.