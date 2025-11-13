from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class User(Base):
    """
    User model for authentication and authorization
    Swedish: Användare
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=False)

    # Access control
    is_admin = Column(Boolean, default=False, nullable=False)  # Super admin - access to all companies
    is_active = Column(Boolean, default=True, nullable=False)  # Account active/suspended

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    company_access = relationship("CompanyUser", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email} (admin={self.is_admin})>"


class CompanyUser(Base):
    """
    Association model for many-to-many relationship between users and companies
    Tracks which users have access to which companies
    Swedish: Företagsanvändare
    """
    __tablename__ = "company_users"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Future: role can be expanded to "admin", "accountant", "viewer", etc.
    role = Column(String(50), default="accountant", nullable=False)

    # Audit
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # Which admin granted access

    # Relationships
    company = relationship("Company", back_populates="users")
    user = relationship("User", back_populates="company_access", foreign_keys=[user_id])
    creator = relationship("User", foreign_keys=[created_by])

    # Constraints
    __table_args__ = (
        UniqueConstraint('company_id', 'user_id', name='uq_company_user'),
    )

    def __repr__(self):
        return f"<CompanyUser company_id={self.company_id} user_id={self.user_id} role={self.role}>"
