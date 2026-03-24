from datetime import date

from pydantic import BaseModel, Field, model_validator


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

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class FiscalYearUpdate(BaseModel):
    """Schema for updating a fiscal year"""

    label: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_closed: bool | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date is not None and self.end_date is not None:
            if self.end_date < self.start_date:
                raise ValueError("end_date must be on or after start_date")
        return self


class FiscalYearResponse(FiscalYearBase):
    """Schema for fiscal year response"""

    id: int
    company_id: int
    is_current: bool = Field(default=False, description="Whether this fiscal year is currently active")

    class Config:
        from_attributes = True
