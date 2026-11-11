"""Local AI code documentation generator backed by an Ollama model."""

from docgen.config import Settings
from docgen.generator import DocGenerationError, DocResult, generate, generate_docs
from docgen.languages import LANGUAGES, UnknownLanguageError, detect_language

__all__ = [
    "LANGUAGES",
    "DocGenerationError",
    "DocResult",
    "Settings",
    "UnknownLanguageError",
    "detect_language",
    "generate",
    "generate_docs",
]
__version__ = "0.2.0"
