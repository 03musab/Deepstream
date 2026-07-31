"""Structured logging for the Deepstream platform."""

import logging
from logging.handlers import RotatingFileHandler
import sys

from deepstream.config import LOG_FILE


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure and return the root Deepstream logger."""
    logger = logging.getLogger("deepstream")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    return logger
