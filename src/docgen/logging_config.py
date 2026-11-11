"""Logging setup shared by the API and any other entry points."""

from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configure the ``docgen`` logger without touching other libraries' loggers."""
    logger = logging.getLogger("docgen")
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
    logger.propagate = False
