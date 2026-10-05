"""Portable archive format — the JSON + files backup.

These Pydantic models ARE the archive format. Every JSON / JSONL file inside a
Reknir archive is a serialisation of one of the models below, and the archive
ships a JSON Schema for each of them under ``schema/`` so a reader on another
stack can validate the files without Reknir's source code.

Conventions (see docs/PORTABLE_ARCHIVE.md):

- amounts are decimal strings with two decimals ("1234.50"), never floats
- dates are ISO ``YYYY-MM-DD``; timestamps are ISO 8601 in UTC with ``Z``
- enums are their string values
- ``id`` fields are archive-local: they are the source primary keys and only
  serve to join rows within one archive. The importer remaps every id.
- users are referenced by email, never by id
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

FORMAT_NAME = "reknir-archive"
FORMAT_VERSION = 1


def _serialize_money(value: Decimal) -> str:
    return f"{Decimal(value).quantize(Decimal('0.01'))}"


def _serialize_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


Money = Annotated[Decimal, PlainSerializer(_serialize_money, return_type=str, when_used="json")]
Timestamp = Annotated[datetime, PlainSerializer(_serialize_datetime, return_type=str, when_used="json")]


class ArchiveModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


class FileEntry(ArchiveModel):
    path: str
    bytes: int
    sha256: str


class CompanyEntry(ArchiveModel):
    org_number: str
    name: str
    path: str  # directory inside the archive, e.g. "companies/556677-8899"


class Manifest(ArchiveModel):
    format: Literal["reknir-archive"] = FORMAT_NAME
    format_version: int = FORMAT_VERSION
    scope: Literal["instance", "company"]
    created_at: Timestamp
    app_version: str
    schema_version: str
    includes_credentials: bool
    includes_ai: bool
    companies: list[CompanyEntry]
    counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    files: list[FileEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Instance level
# ---------------------------------------------------------------------------


class UserRow(ArchiveModel):
    id: int
    email: str
    full_name: str
    is_admin: bool
    is_active: bool
    hashed_password: str | None = None  # bcrypt; only with includes_credentials
    is_service_account: bool = False
    owner_email: str | None = None  # owning user of a service account
    api_key_hash: str | None = None  # only with includes_credentials
    created_at: Timestamp
    updated_at: Timestamp


class AISettingsRow(ArchiveModel):
    ai_enabled: bool
    ollama_url: str
    ollama_model: str
    system_prompt: str | None = None


class BackupScheduleRow(ArchiveModel):
    enabled: bool
    interval_hours: int
    max_backups: int
    preferred_time: str  # "HH:MM"


class InstanceSettings(ArchiveModel):
    ai_settings: AISettingsRow | None = None
    backup_schedule: BackupScheduleRow | None = None


# ---------------------------------------------------------------------------
# Company level
# ---------------------------------------------------------------------------


class CompanyRow(ArchiveModel):
    id: int
    name: str
    org_number: str
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    fiscal_year_start: date
    fiscal_year_end: date
    accounting_basis: str
    vat_reporting_period: str
    is_vat_registered: bool
    logo_filename: str | None = None
    payment_type: str | None = None
    bankgiro_number: str | None = None
    plusgiro_number: str | None = None
    clearing_number: str | None = None
    account_number: str | None = None
    iban: str | None = None
    bic: str | None = None


class CompanyUserRow(ArchiveModel):
    email: str
    role: str
    created_by_email: str | None = None
    created_at: Timestamp


class FiscalYearRow(ArchiveModel):
    id: int
    year: int
    label: str
    start_date: date
    end_date: date
    is_closed: bool


class AccountRow(ArchiveModel):
    id: int
    fiscal_year_id: int
    fiscal_year_label: str
    account_number: int
    name: str
    description: str | None = None
    account_type: str
    opening_balance: Money
    current_balance: Money
    active: bool
    is_bas_account: bool | None = None
    sru_code: str | None = None


class TransactionLineRow(ArchiveModel):
    id: int
    account_id: int
    account_number: int
    debit: Money
    credit: Money
    description: str | None = None


class VerificationRow(ArchiveModel):
    id: int
    fiscal_year_id: int
    series: str
    verification_number: int
    transaction_date: date
    registration_date: date
    description: str
    locked: bool
    created_at: Timestamp
    updated_at: Timestamp
    reverses_verification_id: int | None = None
    reversed_by_verification_id: int | None = None
    lines: list[TransactionLineRow]


class CustomerRow(ArchiveModel):
    id: int
    name: str
    org_number: str | None = None
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str
    payment_terms_days: int
    active: bool


class SupplierRow(CustomerRow):
    payment_type: str | None = None
    bankgiro_number: str | None = None
    plusgiro_number: str | None = None
    clearing_number: str | None = None
    account_number: str | None = None
    iban: str | None = None
    bic: str | None = None


class InvoiceLineRow(ArchiveModel):
    id: int
    description: str
    quantity: Money
    unit: str
    unit_price: Money
    vat_rate: Money
    account_id: int | None = None
    account_number: int | None = None
    net_amount: Money
    vat_amount: Money
    total_amount: Money


class PaymentRow(ArchiveModel):
    id: int
    payment_date: date
    amount: Money
    verification_id: int | None = None
    bank_account_id: int | None = None
    bank_account_number: int | None = None
    reference: str | None = None
    notes: str | None = None
    created_at: Timestamp


class InvoiceRow(ArchiveModel):
    id: int
    customer_id: int
    invoice_number: int
    invoice_series: str
    invoice_date: date
    due_date: date
    paid_date: date | None = None
    reference: str | None = None
    our_reference: str | None = None
    total_amount: Money
    vat_amount: Money
    net_amount: Money
    status: str
    payment_status: str
    paid_amount: Money
    notes: str | None = None
    message: str | None = None
    invoice_verification_id: int | None = None
    payment_verification_id: int | None = None
    pdf_path: str | None = None
    payment_type: str | None = None
    bankgiro_number: str | None = None
    plusgiro_number: str | None = None
    clearing_number: str | None = None
    account_number: str | None = None
    iban: str | None = None
    bic: str | None = None
    created_at: Timestamp
    updated_at: Timestamp
    sent_at: Timestamp | None = None
    lines: list[InvoiceLineRow]
    payments: list[PaymentRow]


class SupplierInvoiceLineRow(ArchiveModel):
    id: int
    description: str
    quantity: Money
    unit_price: Money
    vat_rate: Money
    account_id: int | None = None
    account_number: int | None = None
    net_amount: Money
    vat_amount: Money
    total_amount: Money


class SupplierInvoiceRow(ArchiveModel):
    id: int
    supplier_id: int
    supplier_invoice_number: str
    our_invoice_number: int | None = None
    invoice_date: date
    due_date: date
    paid_date: date | None = None
    total_amount: Money
    vat_amount: Money
    net_amount: Money
    status: str
    payment_status: str
    paid_amount: Money
    ocr_number: str | None = None
    reference: str | None = None
    notes: str | None = None
    invoice_verification_id: int | None = None
    payment_verification_id: int | None = None
    created_at: Timestamp
    updated_at: Timestamp
    lines: list[SupplierInvoiceLineRow]
    payments: list[PaymentRow]


class ExpenseRow(ArchiveModel):
    id: int
    employee_name: str
    expense_date: date
    description: str
    amount: Money
    vat_amount: Money
    expense_account_id: int | None = None
    vat_account_id: int | None = None
    status: str
    approved_date: Timestamp | None = None
    paid_date: Timestamp | None = None
    verification_id: int | None = None
    created_at: Timestamp
    updated_at: Timestamp


class PostingTemplateLineRow(ArchiveModel):
    id: int
    account_number: int
    formula: str
    description: str | None = None
    sort_order: int


class PostingTemplateRow(ArchiveModel):
    id: int
    name: str
    description: str
    default_series: str | None = None
    default_journal_text: str | None = None
    sort_order: int
    created_at: Timestamp
    updated_at: Timestamp
    lines: list[PostingTemplateLineRow]


class DefaultAccountRow(ArchiveModel):
    id: int
    account_type: str
    account_id: int
    account_number: int


class AttachmentLinkRow(ArchiveModel):
    entity_type: str  # supplier_invoice | invoice | expense | verification
    entity_id: int
    role: str
    sort_order: int
    created_at: Timestamp


class AttachmentRow(ArchiveModel):
    id: int
    original_filename: str
    storage_filename: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str | None = None
    status: str
    rejection_reason: str | None = None
    created_at: Timestamp
    created_by_email: str | None = None
    links: list[AttachmentLinkRow]


class PeriodLockRow(ArchiveModel):
    id: int
    locked_through: date
    note: str | None = None
    created_by_email: str | None = None
    created_at: Timestamp


class GapExplanationRow(ArchiveModel):
    id: int
    fiscal_year_id: int
    series: str
    verification_number: int
    explanation: str
    created_by_email: str | None = None
    created_at: Timestamp


class AuditLogRow(ArchiveModel):
    """Behandlingshistorik. record_id refers to the archive-local id of the row in table_name."""

    id: int
    user_email: str | None = None
    action: str
    table_name: str
    record_id: int | None = None
    summary: str
    changes: dict[str, list] | None = None
    created_at: Timestamp


class ChatMessageRow(ArchiveModel):
    id: int
    role: str
    content: str | None = None
    tool_name: str | None = None
    tool_args: str | None = None
    tool_status: str | None = None
    attachment_ids: str | None = None
    created_at: Timestamp


class ChatSessionRow(ArchiveModel):
    id: int
    user_email: str | None = None
    title: str
    created_at: Timestamp
    updated_at: Timestamp
    messages: list[ChatMessageRow]


class AIUploadRow(ArchiveModel):
    id: int
    original_filename: str
    storage_filename: str
    mime_type: str
    size_bytes: int
    created_at: Timestamp
    created_by_email: str | None = None


# Name -> model, used to write schema/*.json into the archive.
SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "manifest": Manifest,
    "user": UserRow,
    "instance_settings": InstanceSettings,
    "company": CompanyRow,
    "company_user": CompanyUserRow,
    "fiscal_year": FiscalYearRow,
    "account": AccountRow,
    "verification": VerificationRow,
    "customer": CustomerRow,
    "supplier": SupplierRow,
    "invoice": InvoiceRow,
    "supplier_invoice": SupplierInvoiceRow,
    "expense": ExpenseRow,
    "posting_template": PostingTemplateRow,
    "default_account": DefaultAccountRow,
    "attachment": AttachmentRow,
    "period_lock": PeriodLockRow,
    "gap_explanation": GapExplanationRow,
    "audit_log": AuditLogRow,
    "chat_session": ChatSessionRow,
    "ai_upload": AIUploadRow,
}
