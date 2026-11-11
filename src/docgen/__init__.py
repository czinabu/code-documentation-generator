"""Local AI code documentation generator backed by an Ollama model."""

from docgen.config import Settings
from docgen.generator import DocGenerationError, generate_docs

__all__ = ["DocGenerationError", "Settings", "generate_docs"]
__version__ = "0.2.0"
