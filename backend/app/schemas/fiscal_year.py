from pydantic import BaseModel, Field
from datetime import date
from typing import Optional


class FiscalYearBase(BaseModel):
    """Base fiscal year schema"""
    year: int = Field(..., ge=1900, le=2100, description="Year (e.g., 2024)")
    label: str = Field(..., min_length=1, max_length=100, description="Display label (e.g., '2024' or '2024/2025')")
    start_date: date
    end_date: date
    is_closed: bool = False


class FiscalYearCreate(BaseModel):
    """Schema for creating a fiscal year"""
    company_id: int
    year: int = Field(..., ge=1900, le=2100)
    label: str = Field(..., min_length=1, max_length=100)
    start_date: date
    end_date: date
    is_closed: bool = False


class FiscalYearUpdate(BaseModel):
    """Schema for updating a fiscal year"""
    label: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_closed: Optional[bool] = None


class FiscalYearResponse(FiscalYearBase):
    """Schema for fiscal year response"""
    id: int
    company_id: int
    is_current: bool = Field(default=False, description="Whether this fiscal year is currently active")

    class Config:
        from_attributes = True
