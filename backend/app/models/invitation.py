"""
Invitation model for inviting users to companies
"""

import secrets
from datetime import datetime, timedelta

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Invitation(Base):
    """
    Model for company invitations

    When a company owner/manager wants to invite someone to their company,
    they create an invitation with a unique token. The invitee can then use
    this token to register and automatically get access to the company.
    """

    __tablename__ = "invitations"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False, default="user")  # user, accountant, manager
    token = Column(String, unique=True, nullable=False, index=True)

    # Expiration
    expires_at = Column(DateTime, nullable=False)

    # Usage tracking
    used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime, nullable=True)
    used_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    company = relationship("Company", back_populates="invitations")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    used_by = relationship("User", foreign_keys=[used_by_user_id])

    @staticmethod
    def generate_token() -> str:
        """Generate a secure random token for invitation"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def create_invitation(company_id: int, created_by_user_id: int, role: str = "user", days_valid: int = 7):
        """
        Create a new invitation

        Args:
            company_id: Company to invite to
            created_by_user_id: User creating the invitation
            role: Role to assign (user, accountant, manager)
            days_valid: Number of days the invitation is valid (default 7)

        Returns:
            Invitation instance (not yet added to session)
        """
        return Invitation(
            company_id=company_id,
            role=role,
            token=Invitation.generate_token(),
            expires_at=datetime.utcnow() + timedelta(days=days_valid),
            created_by_user_id=created_by_user_id,
        )

    def is_valid(self) -> bool:
        """Check if invitation is still valid"""
        return not self.used and datetime.utcnow() < self.expires_at

    def mark_as_used(self, user_id: int):
        """Mark invitation as used"""
        self.used = True
        self.used_at = datetime.utcnow()
        self.used_by_user_id = user_id
