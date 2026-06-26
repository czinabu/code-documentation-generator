from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import ollama
from typing import Dict

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


@app.post("/generate-docs", response_model=Dict[str, str])
def generate_docs(request: CodeRequest) -> Dict[str, str]:
    """
    Generate clean, professional documentation for the provided code snippet.
    """
    if not request.code or not request.code.strip():
        raise HTTPException(status_code=400, detail="Code input cannot be empty.")

    try:
        print(f"DEBUG: Using model: {MODEL_NAME} | Host: {OLLAMA_HOST}")

        client = ollama.Client(host=OLLAMA_HOST)

        response = client.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert technical documentation writer. "
                        "Generate clean, professional, and well-structured Markdown documentation "
                        "for the given code snippet.\n\n"
                        "Rules:\n"
                        "- Use proper Markdown with headings (#, ##, ###)\n"
                        "- Start with a brief overview\n"
                        "- Include Parameters and Returns sections when applicable\n"
                        "- Add a short usage example\n"
                        "- Keep it concise and readable\n"
                        "- Do not add extra explanations or fluff"
                    )
                },
                {
                    "role": "user",
                    "content": request.code
                }
            ]
        )

        documentation = response["message"]["content"].strip()

        return {"documentation": documentation}

    except Exception as e:
        print(f"ERROR: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while generating documentation: {str(e)}"
        )


@app.get("/")
def root():
    return {
        "message": "Local AI Code Documentation Generator is running!",
        "model": MODEL_NAME
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)