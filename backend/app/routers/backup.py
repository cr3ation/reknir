"""Backup and restore API endpoints. Admin only."""

import logging
import shutil
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.database import get_db
from app.dependencies import require_admin
from app.models.backup_schedule import BackupSchedule
from app.models.user import User
from app.services import archive_export_service, archive_import_service, backup_service, restore_service
from app.services.backup_scheduler import signal_reconfigure
from app.services.storage import UPLOADS_DIR

logger = logging.getLogger(__name__)

router = APIRouter()


# ---- Schemas ----


class BackupInfo(BaseModel):
    created_at: str
    app_version: str
    schema_version: str
    filename: str
    size_bytes: int
    format: Literal["json", "sql"] = "json"
    scope: str | None = None
    companies: list[str] = []
    counts: dict[str, int] = {}
    warnings: list[str] = []


class RestoreResponse(BaseModel):
    success: bool
    backup_filename: str
    message: str
    stages_completed: list[str]
    warnings: list[str] = []


class CompanyImportResponse(BaseModel):
    company_ids: list[int]
    created: dict[str, int]
    warnings: list[str]


def _check_backup_filename(filename: str) -> Path:
    # Security: reject path traversal attempts
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename")
    if not backup_service.is_backup_filename(filename):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid backup filename format")
    archive_path = backup_service.BACKUP_DIR / filename
    if not archive_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Backup not found: {filename}")
    return archive_path


class BackupScheduleResponse(BaseModel):
    enabled: bool
    interval_hours: int
    max_backups: int
    preferred_time: str
    last_backup_at: str | None
    next_backup_at: str | None


class BackupScheduleUpdate(BaseModel):
    enabled: bool | None = None
    interval_hours: Literal[6, 24, 48, 168, 336] | None = None
    max_backups: int | None = Field(default=None, ge=1)
    preferred_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")


# ---- Endpoints ----


@router.post("/create", response_model=BackupInfo)
async def create_backup(
    admin: User = Depends(require_admin),
):
    """Create a full backup on the server. Admin only."""
    try:
        archive_path = backup_service.create_backup()
        return backup_service.describe_backup(archive_path)
    except Exception as e:
        logger.error(f"Backup creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backup creation failed: {str(e)}",
        ) from e


@router.get("/list", response_model=list[BackupInfo])
async def list_backups(
    admin: User = Depends(require_admin),
):
    """List all available backup archives on the server. Admin only."""
    return backup_service.list_backups()


@router.get("/download/{filename}")
async def download_backup(
    filename: str,
    admin: User = Depends(require_admin),
):
    """Download a specific backup file from server. Admin only."""
    archive_path = _check_backup_filename(filename)
    return FileResponse(
        path=str(archive_path),
        filename=filename,
        media_type="application/zip" if archive_path.suffix == ".zip" else "application/gzip",
    )


@router.post("/restore/{filename}", response_model=RestoreResponse)
async def restore_from_server(
    filename: str,
    admin: User = Depends(require_admin),
):
    """Restore from a backup file already on the server.

    This is a destructive operation -- all current data will be replaced
    with the backup contents. The restore is all-or-nothing: if any
    validation fails, production remains untouched.

    Admin only.
    """
    archive_path = _check_backup_filename(filename)

    try:
        result = restore_service.restore_from_archive(
            archive_path=archive_path,
            performed_by=admin.email,
        )

        return RestoreResponse(
            success=result.success,
            backup_filename=result.backup_filename,
            message=result.message,
            stages_completed=result.stages_completed,
            warnings=result.warnings,
        )

    except restore_service.RestoreError as e:
        restore_service._log_restore_event(
            backup_filename=filename,
            performed_by=admin.email,
            success=False,
            message=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Restore from server failed unexpectedly: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restore failed: {str(e)}",
        ) from e


@router.post("/restore", response_model=RestoreResponse)
async def restore_backup(
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
):
    """Upload a backup archive and restore the entire system from it.

    This is a destructive operation -- all current data will be replaced
    with the backup contents. The restore is all-or-nothing: if any
    validation fails, production remains untouched.

    Admin only.
    """
    temp_archive = None
    name = file.filename or ""
    suffix = ".zip" if name.endswith(".zip") else ".tar.gz"
    try:
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, prefix="reknir_restore_upload_") as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_archive = Path(tmp.name)

        result = restore_service.restore_from_archive(
            archive_path=temp_archive,
            performed_by=admin.email,
        )

        return RestoreResponse(
            success=result.success,
            backup_filename=name or result.backup_filename,
            message=result.message,
            stages_completed=result.stages_completed,
            warnings=result.warnings,
        )

    except restore_service.RestoreError as e:
        # Log failed attempt
        restore_service._log_restore_event(
            backup_filename="unknown",
            performed_by=admin.email,
            success=False,
            message=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Restore failed unexpectedly: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restore failed: {str(e)}",
        ) from e
    finally:
        if temp_archive and temp_archive.exists():
            temp_archive.unlink()


# ---- Company archives ----


@router.get("/export-company/{company_id}")
async def export_company_archive(
    company_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Download one company as a portable archive (no users, no credentials). Admin only."""
    stamp = datetime.now(UTC).strftime("%Y-%m-%d_%H.%M.%S")
    out_dir = Path(tempfile.mkdtemp(prefix="reknir_company_export_"))
    out_path = out_dir / f"reknir_company_{company_id}_{stamp}.zip"
    try:
        archive_export_service.export_archive(db, out_path, scope="company", company_ids=[company_id])
    except ValueError as e:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return FileResponse(
        path=str(out_path),
        filename=out_path.name,
        media_type="application/zip",
        background=BackgroundTask(shutil.rmtree, out_dir, ignore_errors=True),
    )


@router.post("/import-company", response_model=CompanyImportResponse)
async def import_company_archive(
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Import a company archive as a new company. Existing data is untouched. Admin only."""
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False, prefix="reknir_company_import_") as tmp:
        shutil.copyfileobj(file.file, tmp)
        temp_archive = Path(tmp.name)
    try:
        archive = archive_import_service.verify_archive(temp_archive)
        report = archive_import_service.load_archive(
            db, archive, uploads_target=UPLOADS_DIR, import_users=False, fallback_user=admin
        )
        db.commit()
        archive_import_service.cross_check_sie(db, archive, report)
    except archive_import_service.ArchiveError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    finally:
        temp_archive.unlink(missing_ok=True)
    logger.info(f"Company archive imported by {admin.email}: companies {report.company_ids}")
    return CompanyImportResponse(company_ids=report.company_ids, created=report.created, warnings=report.warnings)


# ---- Delete ----


@router.delete("/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_backup(
    filename: str,
    admin: User = Depends(require_admin),
):
    """Delete a backup file from the server. Admin only."""
    archive_path = _check_backup_filename(filename)
    archive_path.unlink()
    logger.info(f"Backup deleted by {admin.email}: {filename}")


# ---- Schedule ----


def _schedule_to_response(row: BackupSchedule) -> BackupScheduleResponse:
    return BackupScheduleResponse(
        enabled=row.enabled,
        interval_hours=row.interval_hours,
        max_backups=row.max_backups,
        preferred_time=row.preferred_time.strftime("%H:%M") if row.preferred_time else "03:00",
        last_backup_at=row.last_backup_at.isoformat() if row.last_backup_at else None,
        next_backup_at=row.next_backup_at.isoformat() if row.next_backup_at else None,
    )


@router.get("/schedule", response_model=BackupScheduleResponse)
async def get_backup_schedule(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get current backup schedule settings. Admin only."""
    row = db.query(BackupSchedule).filter(BackupSchedule.id == 1).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup schedule not configured",
        )
    return _schedule_to_response(row)


@router.put("/schedule", response_model=BackupScheduleResponse)
async def update_backup_schedule(
    data: BackupScheduleUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update backup schedule settings. Admin only."""
    row = db.query(BackupSchedule).filter(BackupSchedule.id == 1).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup schedule not configured",
        )

    if data.enabled is not None:
        row.enabled = data.enabled
    if data.interval_hours is not None:
        row.interval_hours = data.interval_hours
    if data.max_backups is not None:
        row.max_backups = data.max_backups
    if data.preferred_time is not None:
        h, m = data.preferred_time.split(":")
        from datetime import time as time_type

        row.preferred_time = time_type(int(h), int(m))

    # Compute next_backup_at when enabling or changing interval
    if row.enabled:
        from app.services.backup_scheduler import _compute_next_backup

        interval = timedelta(hours=row.interval_hours)
        preferred = row.preferred_time or time_type(3, 0)
        row.next_backup_at = _compute_next_backup(interval, preferred)
    else:
        row.next_backup_at = None

    row.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)

    signal_reconfigure()
    logger.info(
        f"Backup schedule updated by {admin.email}: enabled={row.enabled}, interval={row.interval_hours}h, max={row.max_backups}"
    )

    return _schedule_to_response(row)
