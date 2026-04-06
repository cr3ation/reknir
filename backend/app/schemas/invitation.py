"""
Pydantic schemas for invitations
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class InvitationCreate(BaseModel):
    """Schema for creating an invitation"""

    company_id: int
    role: str = "user"
    days_valid: int = 7

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed_roles = ["user", "accountant", "manager"]
        if v not in allowed_roles:
            raise ValueError(f'Role must be one of: {", ".join(allowed_roles)}')
        return v

    @field_validator("days_valid")
    @classmethod
    def validate_days_valid(cls, v: int) -> int:
        if v < 1 or v > 30:
            raise ValueError("days_valid must be between 1 and 30")
        return v


class InvitationResponse(BaseModel):
    """Schema for invitation response"""

    id: int
    company_id: int
    role: str
    token: str
    expires_at: datetime
    used: bool
    used_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvitationAccept(BaseModel):
    """Schema for accepting an invitation (registering)"""

    full_name: str
    email: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters long")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email address")
        return v.lower()


class InvitationValidateResponse(BaseModel):
    """Schema for validating invitation token"""

    valid: bool
    company_name: str | None = None
    role: str | None = None
    message: str | None = None
