import enum

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class AttachmentStatus(str, enum.Enum):
    """Attachment processing status"""

    CREATED = "created"  # Metadata created, no file uploaded yet
    UPLOADED = "uploaded"  # File uploaded and verified
    PROCESSING = "processing"  # Scanning/OCR in progress
    READY = "ready"  # Ready for use
    REJECTED = "rejected"  # Rejected (virus, invalid, etc.)


class EntityType(str, enum.Enum):
    """Types of entities that can have attachments"""

    SUPPLIER_INVOICE = "supplier_invoice"
    INVOICE = "invoice"
    EXPENSE = "expense"
    VERIFICATION = "verification"


class AttachmentRole(str, enum.Enum):
    """Role of attachment in relation to entity"""

    ORIGINAL = "original"  # Original document (invoice, receipt)
    RECEIPT = "receipt"  # Payment receipt/confirmation
    SUPPORTING = "supporting"  # Supporting documentation
    CONTRACT = "contract"  # Contract/agreement
    ARCHIVED_PDF = "archived_pdf"  # Canonical snapshot at issuance - immutable


class Attachment(Base):
    """
    Standalone attachment/file resource.
    Can be linked to multiple entities via AttachmentLink.
    """

    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    # File information
    original_filename = Column(String(500), nullable=False)
    storage_filename = Column(String(500), nullable=False, unique=True)  # UUID-based
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    checksum_sha256 = Column(String(64), nullable=True)

    # Status
    status = Column(SQLEnum(AttachmentStatus), default=AttachmentStatus.UPLOADED, nullable=False)
    rejection_reason = Column(String, nullable=True)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    links = relationship("AttachmentLink", back_populates="attachment", cascade="all, delete-orphan")
    company = relationship("Company")
    creator = relationship("User")


class AttachmentLink(Base):
    """
    Links an attachment to an entity (supplier invoice, invoice, expense, verification).
    Supports many-to-many: one attachment can be linked to multiple entities.
    """

    __tablename__ = "attachment_links"

    id = Column(Integer, primary_key=True, index=True)
    attachment_id = Column(Integer, ForeignKey("attachments.id", ondelete="CASCADE"), nullable=False)
    entity_type = Column(SQLEnum(EntityType), nullable=False)
    entity_id = Column(Integer, nullable=False)
    role = Column(SQLEnum(AttachmentRole), default=AttachmentRole.ORIGINAL, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("attachment_id", "entity_type", "entity_id", name="uq_attachment_entity"),
        Index("ix_attachment_links_entity", "entity_type", "entity_id"),
    )

    # Relationships
    attachment = relationship("Attachment", back_populates="links")
