from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import ollama

from languages import LANGUAGES, UnknownLanguageError, detect_language
from prompts import build_messages, clean_output

app = FastAPI(
    title="Local AI Code Documentation Generator",
    description="Generate clean and professional documentation for code using a local Ollama model."
)

# ================== CONFIGURATION ==================
MODEL_NAME = "qwen3:14b"
OLLAMA_HOST = "http://100.65.149.81:11434"   # ← Update with your actual Tailscale IP
# ==================================================


class CodeRequest(BaseModel):
    code: str
    language: Optional[str] = Field(
        default=None,
        description="Language key or alias (e.g. 'python', 'ts', 'go'). Overrides detection.",
    )
    filename: Optional[str] = Field(
        default=None,
        description="Original filename; its extension is used to detect the language.",
    )
    output_format: Literal["markdown", "inline"] = Field(
        default="markdown",
        description="'markdown' for a reference summary, 'inline' for the code with native doc comments added.",
    )


class DocsResponse(BaseModel):
    documentation: str
    language: str
    language_source: str
    output_format: str


@app.post("/generate-docs", response_model=DocsResponse)
def generate_docs(request: CodeRequest) -> DocsResponse:
    """
    Generate documentation for the provided code in the language's native style.
    """
    if not request.code or not request.code.strip():
        raise HTTPException(status_code=400, detail="Code input cannot be empty.")

    try:
        language, source = detect_language(request.code, request.language, request.filename)
    except UnknownLanguageError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        print(f"DEBUG: Using model: {MODEL_NAME} | Host: {OLLAMA_HOST} | "
              f"Language: {language.key} ({source}) | Format: {request.output_format}")

        client = ollama.Client(host=OLLAMA_HOST)

        response = client.chat(
            model=MODEL_NAME,
            messages=build_messages(request.code, language, request.output_format),
        )

        documentation = clean_output(response["message"]["content"], request.output_format)

        return DocsResponse(
            documentation=documentation,
            language=language.key,
            language_source=source,
            output_format=request.output_format,
        )

    except Exception as e:
        print(f"ERROR: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while generating documentation: {str(e)}"
        )


@app.get("/languages")
def list_languages():
    """List supported languages, their file extensions and doc comment style."""
    return [
        {"key": l.key, "name": l.name, "extensions": list(l.extensions), "doc_style": l.doc_style}
        for l in LANGUAGES
    ]


@app.get("/")
def root():
    return {
        "message": "Local AI Code Documentation Generator is running!",
        "model": MODEL_NAME
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)