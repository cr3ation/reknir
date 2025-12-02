from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class FiscalYear(Base):
    """
    Fiscal Year (Räkenskapsår)
    Represents a fiscal/accounting year for a company
    """
    __tablename__ = "fiscal_years"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    # Year identification
    year = Column(Integer, nullable=False, index=True)  # e.g., 2024
    label = Column(String(100), nullable=False)  # e.g., "2024" or "2024/2025"

    # Date range
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    # Status
    is_closed = Column(Boolean, default=False, nullable=False)  # Locked after year-end closing

    # Relationships
    company = relationship("Company", back_populates="fiscal_years")
    verifications = relationship("Verification", back_populates="fiscal_year")
    accounts = relationship("Account", back_populates="fiscal_year")

    def __repr__(self):
        return f"<FiscalYear {self.label} ({self.start_date} - {self.end_date})>"

    @property
    def is_current(self) -> bool:
        """Check if this fiscal year is currently active"""
        from datetime import date
        today = date.today()
        return self.start_date <= today <= self.end_date
