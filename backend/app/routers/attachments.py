import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user, get_user_company_ids, verify_company_access
from app.models.attachment import Attachment, AttachmentLink, AttachmentStatus
from app.models.user import User
from app.schemas.attachment import AttachmentListItem, AttachmentResponse
from app.services import attachment_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    company_id: int = Query(..., description="Company ID"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Upload a new attachment.

    Creates an attachment record and saves the file to storage.
    The attachment is not linked to any entity yet - use the link endpoints on entities to do that.
    """
    logger.info(f"Upload attachment: company_id={company_id}, filename={file.filename}, content_type={file.content_type}")

    # Verify company access
    await verify_company_access(company_id, current_user, db)

    # Validate the upload
    mime_type = attachment_service.validate_upload(file)

    # Generate storage filename
    storage_filename = attachment_service.generate_storage_filename(file.filename)

    # Save file and get size/checksum
    size_bytes, checksum = await attachment_service.save_file(file, storage_filename)

    # Create attachment record
    attachment = Attachment(
        company_id=company_id,
        original_filename=file.filename,
        storage_filename=storage_filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
        checksum_sha256=checksum,
        status=AttachmentStatus.UPLOADED,
        created_by=current_user.id,
    )

    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    return attachment


@router.get("/", response_model=list[AttachmentListItem])
async def list_attachments(
    company_id: int = Query(..., description="Company ID"),
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: None = Depends(verify_company_access),
):
    """List all attachments for a company"""
    attachments = (
        db.query(Attachment)
        .filter(Attachment.company_id == company_id)
        .order_by(Attachment.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return attachments


@router.get("/{attachment_id}", response_model=AttachmentResponse)
async def get_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get attachment metadata"""
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Attachment {attachment_id} not found")

    # Verify access to attachment's company
    await verify_company_access(attachment.company_id, current_user, db)

    return attachment


@router.get("/{attachment_id}/content")
async def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Download attachment file content"""
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Attachment {attachment_id} not found")

    # Verify access to attachment's company
    await verify_company_access(attachment.company_id, current_user, db)

    # Check if file exists
    file_path = attachment_service.get_file_path(attachment.storage_filename)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment file not found on disk")

    return FileResponse(
        path=str(file_path),
        filename=attachment.original_filename,
        media_type=attachment.mime_type,
    )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Delete an attachment.

    Can only delete attachments that are not linked to any entity.
    Use unlink endpoints on entities first if needed.
    """
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Attachment {attachment_id} not found")

    # Verify access to attachment's company
    await verify_company_access(attachment.company_id, current_user, db)

    # Check if attachment has any links
    link_count = db.query(AttachmentLink).filter(AttachmentLink.attachment_id == attachment_id).count()
    if link_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete attachment that is linked to {link_count} entities. Unlink first.",
        )

    # Delete file from storage
    attachment_service.delete_file(attachment.storage_filename)

    # Delete attachment record
    db.delete(attachment)
    db.commit()

    return None
