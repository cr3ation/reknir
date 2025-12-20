from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class TransactionLineBase(BaseModel):
    """Base transaction line schema"""

    account_id: int
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")
    description: str | None = None

    @field_validator("debit", "credit")
    @classmethod
    def validate_amounts(cls, v):
        """Ensure amounts are non-negative"""
        if v < 0:
            raise ValueError("Amounts must be non-negative")
        return v


class TransactionLineCreate(TransactionLineBase):
    """Schema for creating a transaction line"""

    pass


class TransactionLineResponse(TransactionLineBase):
    """Schema for transaction line response"""

    id: int
    verification_id: int
    account_number: int = 0  # Will be populated from account
    account_name: str = ""  # Will be populated from account

    class Config:
        from_attributes = True
        json_encoders = {Decimal: float}


class VerificationBase(BaseModel):
    """Base verification schema"""

    series: str = Field(default="A", max_length=10)
    transaction_date: date
    description: str = Field(..., min_length=1)


class VerificationCreate(VerificationBase):
    """Schema for creating a verification"""

    company_id: int
    fiscal_year_id: int
    transaction_lines: list[TransactionLineCreate] = Field(..., min_length=2)

    @field_validator("transaction_lines")
    @classmethod
    def validate_balance(cls, lines):
        """Ensure debit equals credit"""
        total_debit = sum(line.debit for line in lines)
        total_credit = sum(line.credit for line in lines)

        if abs(total_debit - total_credit) > Decimal("0.01"):
            raise ValueError(f"Verification must balance: Debit={total_debit}, Credit={total_credit}")

        return lines


class VerificationUpdate(BaseModel):
    """Schema for updating a verification"""

    description: str | None = None
    transaction_date: date | None = None


class VerificationResponse(VerificationBase):
    """Schema for verification response"""

    id: int
    company_id: int
    fiscal_year_id: int
    verification_number: int
    registration_date: date
    locked: bool
    created_at: datetime
    updated_at: datetime
    transaction_lines: list[TransactionLineResponse]
    is_balanced: bool
    total_amount: Decimal

    class Config:
        from_attributes = True
        json_encoders = {Decimal: float}


class VerificationListItem(BaseModel):
    """Simplified verification for list views"""

    id: int
    verification_number: int
    series: str
    transaction_date: date
    description: str
    total_amount: Decimal
    locked: bool

    class Config:
        from_attributes = True
        json_encoders = {Decimal: float}
