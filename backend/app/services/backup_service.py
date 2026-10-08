"""Backup service for creating and listing full system backups.

The backup format is the portable JSON + files archive (``reknir_backup_*.zip``,
see ``archive_export_service`` and docs/PORTABLE_ARCHIVE.md): every table as
JSON, every stored file (attachments, logos, AI uploads), SIE4 per fiscal year,
a manifest with SHA-256 for each member, and the JSON Schema of the format.
It needs no PostgreSQL tooling to read and restores into any Reknir version
that understands its ``format_version``.

``create_sql_backup`` still produces the older ``reknir_backup_*.tar.gz``
(pg_dump + attachments) for anyone who wants a byte-exact database copy, and
``restore_service`` can restore both kinds.
"""

import json
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from app import __version__
from app.config import settings
from app.schema_version import get_applied_schema_version
from app.services import archive_export_service, archive_import_service
from app.services.storage import ATTACHMENTS_DIR

logger = logging.getLogger(__name__)

BACKUP_DIR = Path(settings.backup_dir)
BACKUP_PATTERNS = ("reknir_backup_*.zip", "reknir_backup_*.tar.gz")


def is_backup_filename(filename: str) -> bool:
    import fnmatch

    return any(fnmatch.fnmatch(filename, pattern) for pattern in BACKUP_PATTERNS)


def _all_archives() -> list[Path]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    found: list[Path] = []
    for pattern in BACKUP_PATTERNS:
        found.extend(BACKUP_DIR.glob(pattern))
    return sorted(found)


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


def create_backup(include_ai: bool = True) -> Path:
    """Create a full backup as a portable JSON + files archive (.zip).

    Returns:
        Path to the created backup archive.
    """
    from app.database import SessionLocal

    now = datetime.now(UTC)
    timestamp_label = now.strftime("%Y-%m-%d_%H.%M.%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = BACKUP_DIR / f"reknir_backup_{timestamp_label}.zip"
    partial_path = archive_path.with_suffix(".zip.partial")

    db = SessionLocal()
    try:
        manifest = archive_export_service.export_archive(db, partial_path, scope="instance", include_ai=include_ai)
    except Exception:
        partial_path.unlink(missing_ok=True)
        raise
    finally:
        db.close()

    partial_path.replace(archive_path)
    if manifest.warnings:
        logger.warning(f"Backup created with {len(manifest.warnings)} warning(s): {archive_path}")
    logger.info(f"Backup created: {archive_path}")
    return archive_path


def create_sql_backup() -> Path:
    """Create a legacy backup package as a tar.gz archive (pg_dump + attachments).

    Returns:
        Path to the created backup archive.

    Raises:
        RuntimeError: If pg_dump fails or archive creation fails.
    """
    now = datetime.now(UTC)
    timestamp_label = now.strftime("%Y-%m-%d_%H.%M.%S")
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
                "-h",
                db_info["host"],
                "-p",
                db_info["port"],
                "-U",
                db_info["user"],
                "-Fc",
                "-f",
                str(dump_path),
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


def enforce_retention(max_backups: int) -> int:
    """Delete oldest backup archives if count exceeds max_backups.

    Returns:
        Number of backups deleted.
    """
    archives = _all_archives()
    deleted = 0
    while len(archives) > max_backups:
        oldest = archives.pop(0)
        oldest.unlink()
        logger.info(f"Retention: deleted {oldest.name}")
        deleted += 1
    return deleted


def list_backups() -> list[dict]:
    """List all available backup archives with their manifest metadata.

    Returns:
        List of dicts with created_at, app_version, schema_version, format
        ("json" or "sql"), filename, size_bytes, and for json archives also
        companies, counts and warnings.
    """
    backups = []

    for archive_path in reversed(_all_archives()):
        try:
            backups.append(describe_backup(archive_path))
        except Exception as e:
            logger.warning(f"Could not read manifest from {archive_path}: {e}")

    return backups


def describe_backup(archive_path: Path) -> dict:
    """Read the manifest of one backup archive (either format)."""
    if archive_path.suffix == ".zip":
        manifest = archive_import_service.read_manifest(archive_path)
        info = {
            "created_at": manifest.created_at.isoformat(),
            "app_version": manifest.app_version,
            "schema_version": manifest.schema_version,
            "format": "json",
            "format_version": manifest.format_version,
            "scope": manifest.scope,
            "companies": [c.name for c in manifest.companies],
            "counts": manifest.counts,
            "warnings": manifest.warnings,
        }
    else:
        with tarfile.open(archive_path, "r:gz") as tar:
            f = tar.extractfile(tar.getmember("backup/manifest.json"))
            if f is None:
                raise RuntimeError("manifest not readable")
            info = json.loads(f.read())
        info["format"] = "sql"
    info["filename"] = archive_path.name
    info["size_bytes"] = archive_path.stat().st_size
    return info
