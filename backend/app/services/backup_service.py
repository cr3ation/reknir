"""Backup service for creating and listing full system backups.

A backup is a tar.gz archive containing:
- manifest.json: version metadata
- database_dump: pg_dump in custom format
- files/: all attachment files
"""

import json
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app import __version__
from app.config import settings
from app.schema_version import get_applied_schema_version
from app.services.attachment_service import ATTACHMENTS_DIR

logger = logging.getLogger(__name__)

BACKUP_DIR = Path(settings.backup_dir)


def _parse_database_url(url: str) -> dict:
    """Parse DATABASE_URL into components for pg_dump/pg_restore."""
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "user": parsed.username or "reknir",
        "password": parsed.password or "",
        "dbname": (parsed.path or "/reknir").lstrip("/"),
    }


def create_backup() -> Path:
    """Create a full backup package as a tar.gz archive.

    Returns:
        Path to the created backup archive.

    Raises:
        RuntimeError: If pg_dump fails or archive creation fails.
    """
    now = datetime.now(timezone.utc)
    timestamp_label = now.strftime("%Y%m%d_%H%M%S")
    timestamp = now.isoformat()

    with tempfile.TemporaryDirectory(prefix="reknir_backup_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Create manifest.json
        manifest = {
            "created_at": timestamp,
            "app_version": __version__,
            "schema_version": get_applied_schema_version(),
        }
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

        # 2. Run pg_dump (custom format for pg_restore compatibility)
        db_info = _parse_database_url(settings.database_url)
        dump_path = tmp_path / "database_dump"
        env = {**os.environ, "PGPASSWORD": db_info["password"]}

        result = subprocess.run(
            [
                "pg_dump",
                "-h", db_info["host"],
                "-p", db_info["port"],
                "-U", db_info["user"],
                "-Fc",
                "-f", str(dump_path),
                db_info["dbname"],
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )

        if result.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {result.stderr}")

        # 3. Copy attachment files
        files_dir = tmp_path / "files"
        if ATTACHMENTS_DIR.exists() and any(ATTACHMENTS_DIR.iterdir()):
            shutil.copytree(ATTACHMENTS_DIR, files_dir)
        else:
            files_dir.mkdir()

        # 4. Create tar.gz archive
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        archive_name = f"reknir_backup_{timestamp_label}.tar.gz"
        archive_path = BACKUP_DIR / archive_name

        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(str(manifest_path), arcname="backup/manifest.json")
            tar.add(str(dump_path), arcname="backup/database_dump")
            tar.add(str(files_dir), arcname="backup/files")

        logger.info(f"Backup created: {archive_path}")
        return archive_path


def list_backups() -> list[dict]:
    """List all available backup archives with their manifest metadata.

    Returns:
        List of dicts with created_at, app_version,
        schema_version, filename, size_bytes.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backups = []

    for archive_path in sorted(BACKUP_DIR.glob("reknir_backup_*.tar.gz"), reverse=True):
        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                manifest_member = tar.getmember("backup/manifest.json")
                f = tar.extractfile(manifest_member)
                if f is None:
                    continue
                manifest = json.loads(f.read())
                manifest["filename"] = archive_path.name
                manifest["size_bytes"] = archive_path.stat().st_size
                backups.append(manifest)
        except Exception as e:
            logger.warning(f"Could not read manifest from {archive_path}: {e}")

    return backups
