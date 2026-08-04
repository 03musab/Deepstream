"""Structured logging for the Deepstream platform."""

import logging
from logging.handlers import RotatingFileHandler
import sys

from deepstream.config import LOG_FILE


def _console_safe_stream():
    """Return ``sys.stdout`` configured so unicode (e.g. ``\u2192``) never
    crashes console logging on encodings that cannot represent it.

    Windows pipes/redirection default to the cp1252 codec, which cannot encode
    the arrow characters used in pair names; ``StreamHandler`` would then emit
    a spurious ``UnicodeEncodeError`` traceback for every such log line. The
    file handler writes UTF-8, so the full characters are always preserved in
    the log file — the console only degrades undisplayable characters to ``?``.
    """
    stream = sys.stdout
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(errors="replace")
        except (OSError, ValueError):
            # stdout is not a reconfigurable text stream (e.g. replaced by the
            # caller); logging must keep working regardless.
            pass
    return stream


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

    console_handler = logging.StreamHandler(_console_safe_stream())
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    return logger
