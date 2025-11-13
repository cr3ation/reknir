"""
Pydantic schemas for invitations
"""
from pydantic import BaseModel, validator
from datetime import datetime
from typing import Optional


class InvitationCreate(BaseModel):
    """Schema for creating an invitation"""
    company_id: int
    role: str = "user"
    days_valid: int = 7

    @validator('role')
    def validate_role(cls, v):
        allowed_roles = ['user', 'accountant', 'manager']
        if v not in allowed_roles:
            raise ValueError(f'Role must be one of: {", ".join(allowed_roles)}')
        return v

    @validator('days_valid')
    def validate_days_valid(cls, v):
        if v < 1 or v > 30:
            raise ValueError('days_valid must be between 1 and 30')
        return v


class InvitationResponse(BaseModel):
    """Schema for invitation response"""
    id: int
    company_id: int
    role: str
    token: str
    expires_at: datetime
    used: bool
    used_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class InvitationAccept(BaseModel):
    """Schema for accepting an invitation (registering)"""
    full_name: str
    email: str
    password: str

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v

    @validator('email')
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email address')
        return v.lower()


class InvitationValidateResponse(BaseModel):
    """Schema for validating invitation token"""
    valid: bool
    company_name: Optional[str] = None
    role: Optional[str] = None
    message: Optional[str] = None
