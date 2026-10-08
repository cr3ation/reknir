"""File storage locations.

Everything Reknir stores on disk lives under ``settings.uploads_dir`` (default
``/app/uploads``, a bind mount in docker-compose). The portable archive mirrors
this layout under ``files/`` and a restore swaps these sub-directories.
"""

import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path(settings.uploads_dir)
ATTACHMENTS_DIR = UPLOADS_DIR / "attachments"
LOGOS_DIR = UPLOADS_DIR / "logos"
AI_UPLOADS_DIR = UPLOADS_DIR / "ai_uploads"

STORAGE_SUBDIRS = ("attachments", "logos", "ai_uploads")


def ensure_storage_dirs() -> None:
    """Create the storage directories if possible. Missing permissions only log a warning
    so that tooling (tests, CLI verify) can import the app without a writable uploads dir."""
    for sub in (ATTACHMENTS_DIR, LOGOS_DIR, AI_UPLOADS_DIR):
        try:
            sub.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(f"Could not create storage directory {sub}: {e}")


ensure_storage_dirs()
