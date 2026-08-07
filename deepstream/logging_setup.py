"""Structured logging for the Deepstream platform."""

import logging
from logging.handlers import RotatingFileHandler
import sys

from deepstream.config import LOG_FILE


def make_console_unicode_safe() -> None:
    """Best-effort: make the console tolerate unicode it cannot encode.

    Windows pipes/redirection default to the cp1252 codec, which cannot encode
    characters such as ``→`` (pair names) or emoji. After this call, stdout
    degrades undisplayable characters to ``?`` instead of raising a spurious
    ``UnicodeEncodeError`` traceback. Files are written UTF-8 regardless, so
    nothing is lost on disk.
    """
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(errors="replace")
        except (OSError, ValueError):
            # stdout is not a reconfigurable text stream (e.g. replaced by the
            # caller); callers must keep working regardless.
            pass


def _console_safe_stream():
    """Return ``sys.stdout`` after making it unicode-safe (see above)."""
    make_console_unicode_safe()
    return sys.stdout


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
