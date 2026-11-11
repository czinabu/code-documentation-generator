"""FastAPI application."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from docgen import __version__
from docgen.config import Settings
from docgen.generator import DocGenerationError, generate
from docgen.languages import LANGUAGES
from docgen.logging_config import configure_logging


class CodeRequest(BaseModel):
    code: str
    language: str | None = Field(
        default=None,
        description="Language key or alias (e.g. 'python', 'ts', 'golang'). Overrides detection.",
    )
    filename: str | None = Field(
        default=None,
        description="Original filename; its extension is used to detect the language.",
    )
    output_format: Literal["markdown", "inline"] = Field(
        default="markdown",
        description="'markdown' for a reference summary, 'inline' for the code with "
        "native doc comments added.",
    )


class DocsResponse(BaseModel):
    documentation: str
    language: str
    language_source: Literal["request", "filename", "content", "fallback"]
    output_format: Literal["markdown", "inline"]


class LanguageInfo(BaseModel):
    key: str
    name: str
    extensions: list[str]
    doc_style: str


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
    def generate_docs_endpoint(request: CodeRequest, settings: SettingsDep) -> DocsResponse:
        """Generate documentation in the code's native style."""
        try:
            result = generate(
                request.code,
                language=request.language,
                filename=request.filename,
                output_format=request.output_format,
                settings=settings,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except DocGenerationError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return DocsResponse(
            documentation=result.documentation,
            language=result.language.key,
            language_source=result.language_source,
            output_format=result.output_format,
        )

    @app.get("/languages", response_model=list[LanguageInfo])
    def languages() -> list[LanguageInfo]:
        """List supported languages, their file extensions and doc comment style."""
        return [
            LanguageInfo(
                key=lang.key,
                name=lang.name,
                extensions=list(lang.extensions),
                doc_style=lang.doc_style,
            )
            for lang in LANGUAGES
        ]

    return app
