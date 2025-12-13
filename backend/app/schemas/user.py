from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List


# ==================== User Schemas ====================

class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=200)


class UserCreate(UserBase):
    """Schema for creating a user"""
    password: str = Field(..., min_length=8, max_length=100)


class UserUpdate(BaseModel):
    """Schema for updating a user"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=200)
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Schema for user response (without sensitive data)"""
    id: int
    is_admin: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserWithCompanies(UserResponse):
    """User response with list of company IDs they have access to"""
    company_ids: List[int] = []


# ==================== Auth Schemas ====================

class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Data encoded in JWT token"""
    user_id: int
    email: str
    is_admin: bool


class LoginRequest(BaseModel):
    """Login request with email/password"""
    email: EmailStr
    password: str


# ==================== CompanyUser Schemas ====================

class CompanyUserBase(BaseModel):
    """Base company-user association schema"""
    company_id: int
    user_id: int
    role: str = "accountant"


class CompanyUserCreate(BaseModel):
    """Schema for granting user access to company"""
    user_id: int
    role: str = "accountant"


class CompanyUserResponse(CompanyUserBase):
    """Schema for company-user response"""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class CompanyAccessRequest(BaseModel):
    """Request to grant/modify company access"""
    role: str = Field(default="accountant", description="User role in this company")
