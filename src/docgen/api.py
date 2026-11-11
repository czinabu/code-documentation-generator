"""FastAPI application."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from docgen import __version__
from docgen.config import Settings
from docgen.generator import DocGenerationError, generate_docs
from docgen.logging_config import configure_logging


class CodeRequest(BaseModel):
    code: str


class DocsResponse(BaseModel):
    documentation: str


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_settings)]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Pass ``settings`` to override env/file configuration."""
    settings = settings or Settings.load()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Local AI Code Documentation Generator",
        description="Generate clean and professional documentation for code "
        "using a local Ollama model.",
        version=__version__,
    )
    app.state.settings = settings

    @app.get("/")
    def root(settings: SettingsDep) -> dict[str, str]:
        return {
            "message": "Local AI Code Documentation Generator is running!",
            "model": settings.model,
        }

    @app.post("/generate-docs", response_model=DocsResponse)
    def generate(request: CodeRequest, settings: SettingsDep) -> DocsResponse:
        """Generate documentation for the provided code snippet."""
        try:
            documentation = generate_docs(request.code, settings=settings)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except DocGenerationError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return DocsResponse(documentation=documentation)

    return app
