from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ReversalCreate(BaseModel):
    description: str | None = Field(default=None, max_length=500)
    transaction_date: date | None = None


class GapItem(BaseModel):
    series: str
    verification_number: int
    explanation: str | None = None


class GapExplanationCreate(BaseModel):
    company_id: int
    fiscal_year_id: int
    series: str = Field(..., max_length=10)
    verification_number: int
    explanation: str = Field(..., min_length=3, max_length=2000)


class PeriodLockCreate(BaseModel):
    locked_through: date
    note: str | None = Field(default=None, max_length=255)


class PeriodLockResponse(BaseModel):
    id: int
    locked_through: date
    note: str | None
    created_by: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PeriodLockStatus(BaseModel):
    locked_through: date | None
    history: list[PeriodLockResponse]


class AuditLogEntry(BaseModel):
    id: int
    company_id: int | None
    user_email: str | None
    action: str
    table_name: str
    record_id: int | None
    summary: str
    changes: dict | None
    created_at: datetime
