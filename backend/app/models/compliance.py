"""Compliance tables: period locks, verification-gap explanations and the audit log."""

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class PeriodLock(Base):
    """A company's books are locked through ``locked_through`` (inclusive).

    Every lock is a new row, so the history of who locked what and when stays.
    The effective lock is the latest ``locked_through``.
    """

    __tablename__ = "period_locks"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    locked_through = Column(Date, nullable=False)
    note = Column(String(255), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    creator = relationship("User")


class VerificationGapExplanation(Base):
    """Why a number is missing in a verification series (BFNAR 2013:2 asks for this)."""

    __tablename__ = "verification_gap_explanations"
    __table_args__ = (
        UniqueConstraint("company_id", "fiscal_year_id", "series", "verification_number", name="uq_gap_explanation"),
    )

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    fiscal_year_id = Column(Integer, ForeignKey("fiscal_years.id", ondelete="CASCADE"), nullable=False)
    series = Column(String(10), nullable=False)
    verification_number = Column(Integer, nullable=False)
    explanation = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AuditLog(Base):
    """Who changed what. Written by mapper events (see audit_service), never edited."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, nullable=True, index=True)
    user_email = Column(String(255), nullable=True)
    action = Column(String(10), nullable=False)  # insert | update | delete | note
    table_name = Column(String(64), nullable=False, index=True)
    record_id = Column(Integer, nullable=True, index=True)
    summary = Column(Text, nullable=False)
    changes = Column(Text, nullable=True)  # JSON: {"field": [old, new]}
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
