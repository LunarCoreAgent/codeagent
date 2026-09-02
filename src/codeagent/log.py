"""Persistent run logging: every session appended to ~/.codeagent/logs/.

Uses a rotating file handler (1 MB × 5 backups). Level controlled by the
``CODEAGENT_LOG_LEVEL`` env var (default INFO). Library users call
``setup_logging()`` once; the CLI does it automatically per command.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("~/.codeagent/logs")
LOG_FILE = LOG_DIR / "codeagent.log"

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOGGER_NAME = "codeagent"
_configured = False


def setup_logging(level: str | int | None = None, log_file: Path | None = None) -> Path:
    """Attach a rotating file handler to the ``codeagent`` logger tree.

    Idempotent — repeated calls reuse the first configuration. Returns the
    active log file path.
    """
    global _configured
    path = Path(log_file).expanduser() if log_file else Path(LOG_FILE).expanduser()
    if _configured:
        return path

    if level is None:
        level = os.environ.get("CODEAGENT_LOG_LEVEL", "INFO")
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        path, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(_FORMAT))

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False

    _configured = True
    return path


def get_logger(name: str) -> logging.Logger:
    """Child logger under the ``codeagent`` tree (e.g. ``codeagent.agent``)."""
    return logging.getLogger(f"{_LOGGER_NAME}.{name}")


def tail_log(lines: int = 50, log_file: Path | None = None) -> list[str]:
    """Return the last ``lines`` lines of the active log file."""
    path = Path(log_file).expanduser() if log_file else Path(LOG_FILE).expanduser()
    if not path.is_file():
        return []
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return content[-lines:]
