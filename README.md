# FastAPI + Ollama + Qwen Documentation Generator

This is a FastAPI application that uses the Ollama Python client to generate documentation for code snippets using the Qwen model.

## Features
- Accepts a code snippet via a POST request
- Uses the Qwen model from Ollama to generate documentation
- Returns documentation in Markdown format
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

### 5. Access the Root Endpoint

You can access the root endpoint at `http://localhost:8000` to see a simple status message and the current model being used.

---

## Configuration

You can customize the following in your `main.py` file:

- `MODEL_NAME`: Change this to use a different model (e.g., `"qwen2.5:14b"`).
- `OLLAMA_HOST`: Update this if you're connecting to a remote Ollama server (e.g., via Tailscale).

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.