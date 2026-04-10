"""
AutoPitch v3 — Structured Logging
Rotating file handler + console output. All modules import `logger` from here.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "autopitch.log")
MAX_BYTES = 2_000_000
BACKUP_COUNT = 3


def _setup() -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)

    log = logging.getLogger("autopitch")
    log.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler — INFO and above
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    log.addHandler(console)

    # File handler — DEBUG and above, with rotation
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    log.addHandler(file_handler)

    return log


logger = _setup()