from datetime import datetime

from pydantic import BaseModel

from app.models.attachment import AttachmentRole, AttachmentStatus, EntityType


class AttachmentResponse(BaseModel):
    """Response schema for attachment metadata"""

    id: int
    company_id: int
    original_filename: str
    storage_filename: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str | None = None
    status: AttachmentStatus
    rejection_reason: str | None = None
    created_at: datetime
    created_by: int

    class Config:
        from_attributes = True


class AttachmentListItem(BaseModel):
    """Simplified schema for attachment lists"""

    id: int
    original_filename: str
    mime_type: str
    size_bytes: int
    status: AttachmentStatus
    created_at: datetime

    class Config:
        from_attributes = True


class AttachmentLinkCreate(BaseModel):
    """Schema for linking an attachment to an entity"""

    attachment_id: int
    role: AttachmentRole = AttachmentRole.ORIGINAL
    sort_order: int = 0


class AttachmentLinkResponse(BaseModel):
    """Response schema for attachment link with attachment details"""

    id: int
    attachment_id: int
    entity_type: EntityType
    entity_id: int
    role: AttachmentRole
    sort_order: int
    created_at: datetime

    # Include attachment details for convenience
    attachment: AttachmentListItem

    class Config:
        from_attributes = True


class AttachmentWithLinksResponse(AttachmentResponse):
    """Attachment response with links included"""

    links: list[AttachmentLinkResponse] = []

    class Config:
        from_attributes = True


class EntityAttachmentItem(BaseModel):
    """Attachment item when listing attachments for an entity"""

    link_id: int
    attachment_id: int
    role: AttachmentRole
    sort_order: int
    created_at: datetime

    # Attachment details
    original_filename: str
    mime_type: str
    size_bytes: int
    status: AttachmentStatus

    class Config:
        from_attributes = True
