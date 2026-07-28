from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.year_end_closing import AdjustmentType, ClosingStatus, ClosingStep

# Depreciation needs a fixed asset register to propose an amount from, and reknir has
# none, so the wizard does not offer it even though the enum reserves the value.
OFFERED_ADJUSTMENT_TYPES = tuple(t for t in AdjustmentType if t != AdjustmentType.DEPRECIATION)


class AdjustmentInput(BaseModel):
    """One answer in the adjustments step"""

    adjustment_type: AdjustmentType
    amount: Decimal
    balance_account_id: int | None = None
    result_account_id: int | None = None
    description: str | None = None

    @field_validator("adjustment_type")
    @classmethod
    def validate_offered(cls, value: AdjustmentType) -> AdjustmentType:
        if value not in OFFERED_ADJUSTMENT_TYPES:
            raise ValueError(
                f"Adjustment type {value.value} is not available yet. "
                "Depreciation requires a fixed asset register, which reknir does not have."
            )
        return value


class AdjustmentResponse(BaseModel):
    """A stored adjustment answer"""

    id: int
    adjustment_type: AdjustmentType
    amount: Decimal
    balance_account_id: int | None
    result_account_id: int | None
    description: str | None

    model_config = ConfigDict(from_attributes=True)


class PostingLineResponse(BaseModel):
    """One line of a posting the closing will make"""

    account_number: int
    account_name: str
    debit: Decimal
    credit: Decimal
    account_will_be_created: bool


class ProposedPostingResponse(BaseModel):
    """A verification that will be created when the closing is completed"""

    kind: str
    description: str
    transaction_date: date
    lines: list[PostingLineResponse]


class CheckResponse(BaseModel):
    """One traffic light result"""

    code: str
    severity: str
    message: str
    detail: str | None = None


class StepResponse(BaseModel):
    """A wizard step and whether the user may open it"""

    step: ClosingStep
    is_unlocked: bool
    is_current: bool


class YearEndClosingResponse(BaseModel):
    """
    The whole closing document.

    Every endpoint returns this same shape, recomputed, so the wizard has one response
    model and one renderer regardless of what the user just did.
    """

    id: int
    company_id: int
    fiscal_year_id: int
    fiscal_year_label: str
    status: ClosingStatus
    current_step: ClosingStep
    steps: list[StepResponse]

    preparation_confirmed: bool
    bank_statement_balance: Decimal | None
    booked_bank_balance: Decimal | None
    acknowledged_warnings: list[str]

    adjustments: list[AdjustmentResponse]
    checks: list[CheckResponse]

    result_before_tax: Decimal
    tax: Decimal
    result_after_tax: Decimal
    tax_amount_override: Decimal | None
    postings: list[ProposedPostingResponse]

    can_complete: bool
    completed_at: datetime | None


class YearEndClosingUpdate(BaseModel):
    """
    The single mutation covering all four steps.

    Every field is optional; only what is sent is changed. Sending adjustments replaces
    the whole list, which keeps the step idempotent — the same request twice leaves the
    same state rather than accumulating duplicates.
    """

    current_step: ClosingStep | None = None
    preparation_confirmed: bool | None = None
    bank_statement_balance: Decimal | None = None
    acknowledged_warnings: list[str] | None = None
    tax_amount_override: Decimal | None = None
    adjustments: list[AdjustmentInput] | None = None


class ReopenRequest(BaseModel):
    """Reopening is logged, so a reason is required"""

    reason: str = Field(..., min_length=1, max_length=1000)
