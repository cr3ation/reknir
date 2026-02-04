"""Backup and restore API endpoints. Admin only."""

import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.dependencies import require_admin
from app.models.user import User
from app.services import backup_service
from app.services import restore_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ---- Schemas ----


class BackupInfo(BaseModel):
    backup_id: str
    created_at: str
    app_version: str
    schema_version: str
    filename: str
    size_bytes: int


class RestoreResponse(BaseModel):
    success: bool
    backup_id: str
    message: str
    stages_completed: list[str]


# ---- Endpoints ----


@router.post("/create", response_class=FileResponse)
async def create_backup(
    admin: User = Depends(require_admin),
):
    """Create a full backup and return it as a downloadable .tar.gz file. Admin only."""
    try:
        archive_path = backup_service.create_backup()
        return FileResponse(
            path=str(archive_path),
            filename=archive_path.name,
            media_type="application/gzip",
        )
    except Exception as e:
        logger.error(f"Backup creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backup creation failed: {str(e)}",
        )


@router.get("/list", response_model=list[BackupInfo])
async def list_backups(
    admin: User = Depends(require_admin),
):
    """List all available backup archives on the server. Admin only."""
    return backup_service.list_backups()


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
    try:
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(
            suffix=".tar.gz", delete=False, prefix="reknir_restore_upload_"
        ) as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_archive = Path(tmp.name)

        result = restore_service.restore_from_archive(
            archive_path=temp_archive,
            performed_by=admin.email,
        )

        return RestoreResponse(
            success=result.success,
            backup_id=result.backup_id,
            message=result.message,
            stages_completed=result.stages_completed,
        )

    except restore_service.RestoreError as e:
        # Log failed attempt
        restore_service._log_restore_event(
            backup_id="unknown",
            performed_by=admin.email,
            success=False,
            message=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Restore failed unexpectedly: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restore failed: {str(e)}",
        )
    finally:
        if temp_archive and temp_archive.exists():
            temp_archive.unlink()
