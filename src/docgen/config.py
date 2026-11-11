"""Runtime configuration.

Settings are resolved in this order (later wins):

1. Built-in defaults.
2. A TOML file, if ``DOCGEN_CONFIG`` points to one (or ``docgen.toml`` exists
   in the working directory).
3. Environment variables.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_FILE = "docgen.toml"

# Environment variable -> Settings field. The first match wins, so the
# DOCGEN_-prefixed name takes priority over Ollama's own OLLAMA_HOST.
ENV_VARS: dict[str, tuple[str, ...]] = {
    "model": ("DOCGEN_MODEL",),
    "ollama_host": ("DOCGEN_OLLAMA_HOST", "OLLAMA_HOST"),
    "timeout": ("DOCGEN_TIMEOUT",),
    "log_level": ("DOCGEN_LOG_LEVEL",),
}


class ConfigError(ValueError):
    """Raised when configuration values are invalid."""


@dataclass(frozen=True)
class Settings:
    model: str = "qwen3:14b"
    ollama_host: str = "http://localhost:11434"
    timeout: float = 120.0
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if self.timeout <= 0:
            raise ConfigError(f"timeout must be positive, got {self.timeout}")
        if not self.model.strip():
            raise ConfigError("model must not be empty")

    @classmethod
    def load(
        cls,
        env: Mapping[str, str] | None = None,
        config_file: str | Path | None = None,
    ) -> Settings:
        """Build settings from defaults, an optional TOML file and the environment."""
        env = os.environ if env is None else env
        settings = cls()

        path = config_file or env.get("DOCGEN_CONFIG")
        if path is None and Path(DEFAULT_CONFIG_FILE).is_file():
            path = DEFAULT_CONFIG_FILE
        if path is not None:
            settings = replace(settings, **_read_toml(Path(path)))

        overrides: dict[str, Any] = {}
        for field_name, names in ENV_VARS.items():
            for name in names:
                if env.get(name):
                    overrides[field_name] = env[name]
                    break
        return replace(settings, **_coerce(overrides))


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from exc

    # Allow either top-level keys or a [docgen] table.
    data = data.get("docgen", data)
    known = {f.name for f in fields(Settings)}
    unknown = set(data) - known
    if unknown:
        raise ConfigError(f"unknown config keys in {path}: {', '.join(sorted(unknown))}")
    return _coerce(data)


def _coerce(values: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(values)
    if "timeout" in out:
        try:
            out["timeout"] = float(out["timeout"])
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"timeout must be a number, got {out['timeout']!r}") from exc
    if "log_level" in out:
        out["log_level"] = str(out["log_level"]).upper()
    return out
