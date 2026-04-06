from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer

from app.database import Base


class BackupSchedule(Base):
    """Single-row table for automated backup configuration."""

    __tablename__ = "backup_schedule"

    id = Column(Integer, primary_key=True)
    enabled = Column(Boolean, default=False, nullable=False)
    interval_hours = Column(Integer, default=24, nullable=False)
    max_backups = Column(Integer, default=30, nullable=False)
    last_backup_at = Column(DateTime(timezone=True), nullable=True)
    next_backup_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<BackupSchedule enabled={self.enabled} interval={self.interval_hours}h>"
