"""Export a Reknir instance (or one company) as a portable JSON + files archive.

Layout of the produced zip (see docs/PORTABLE_ARCHIVE.md):

    manifest.json
    schema/<name>.schema.json
    instance/users.json                 (scope=instance)
    instance/settings.json              (scope=instance)
    companies/<orgnr>/company.json
    companies/<orgnr>/company_users.json
    companies/<orgnr>/fiscal_years.json
    companies/<orgnr>/accounts.jsonl
    companies/<orgnr>/verifications.jsonl
    companies/<orgnr>/customers.json
    companies/<orgnr>/suppliers.json
    companies/<orgnr>/invoices.jsonl
    companies/<orgnr>/supplier_invoices.jsonl
    companies/<orgnr>/expenses.jsonl
    companies/<orgnr>/posting_templates.json
    companies/<orgnr>/default_accounts.json
    companies/<orgnr>/attachments.jsonl
    companies/<orgnr>/ai/chat_sessions.jsonl   (includes_ai)
    companies/<orgnr>/ai/uploads.jsonl          (includes_ai)
    companies/<orgnr>/sie/<fiscal year label>.se
    files/attachments/<storage_filename>
    files/logos/<logo_filename>
    files/ai_uploads/<storage_filename>         (includes_ai)

``files/`` mirrors the uploads directory on disk, so a restore is a directory swap.
"""

from __future__ import annotations

import enum
import hashlib
import json
import logging
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.models.account import Account
from app.models.ai_assistant import AISettings, AIUpload, ChatSession
from app.models.attachment import Attachment
from app.models.backup_schedule import BackupSchedule
from app.models.company import Company
from app.models.customer import Customer, Supplier
from app.models.default_account import DefaultAccount
from app.models.expense import Expense
from app.models.fiscal_year import FiscalYear
from app.models.invoice import Invoice, SupplierInvoice
from app.models.posting_template import PostingTemplate
from app.models.user import CompanyUser, User
from app.models.verification import Verification
from app.schemas import archive as fmt
from app.services.sie4_service import export_sie4
from app.services.storage import UPLOADS_DIR

logger = logging.getLogger(__name__)

ATTACHMENTS_SUBDIR = "attachments"
LOGOS_SUBDIR = "logos"
AI_UPLOADS_SUBDIR = "ai_uploads"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _val(value: Any) -> Any:
    """Enum -> its value; everything else unchanged."""
    if isinstance(value, enum.Enum):
        return value.value
    return value


def _fields(obj: Any, names: list[str]) -> dict[str, Any]:
    return {name: _val(getattr(obj, name)) for name in names}


def _company_dirname(org_number: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z-]", "", org_number)
    return safe or "company"


def _schema_version(db: Session) -> str:
    """Alembic revision of the database being exported ("unknown" without an alembic table)."""
    try:
        row = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
        return row[0] if row else "unknown"
    except Exception:
        db.rollback()
        return "unknown"


class _ZipWriter:
    """Writes members into a zip while recording size and SHA-256 for the manifest."""

    def __init__(self, path: Path):
        self.zip = zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED)
        self.entries: list[fmt.FileEntry] = []

    def write_text(self, name: str, text: str) -> None:
        data = text.encode("utf-8")
        self.zip.writestr(name, data)
        self.entries.append(fmt.FileEntry(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))

    def write_json(self, name: str, rows: list[fmt.ArchiveModel]) -> None:
        self.write_text(name, "[\n" + ",\n".join(r.model_dump_json() for r in rows) + "\n]\n")

    def write_jsonl(self, name: str, rows: list[fmt.ArchiveModel]) -> None:
        self.write_text(name, "".join(r.model_dump_json() + "\n" for r in rows))

    def write_file(self, name: str, source: Path) -> None:
        digest = hashlib.sha256()
        size = 0
        with open(source, "rb") as src, self.zip.open(name, "w", force_zip64=True) as dst:
            while chunk := src.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
                dst.write(chunk)
        self.entries.append(fmt.FileEntry(path=name, bytes=size, sha256=digest.hexdigest()))

    def close(self) -> None:
        self.zip.close()


# ---------------------------------------------------------------------------
# row builders (ORM -> archive rows)
# ---------------------------------------------------------------------------

_COMPANY_FIELDS = [
    "id", "name", "org_number", "address", "postal_code", "city", "phone", "email",
    "fiscal_year_start", "fiscal_year_end", "accounting_basis", "vat_reporting_period",
    "is_vat_registered", "logo_filename", "payment_type", "bankgiro_number", "plusgiro_number",
    "clearing_number", "account_number", "iban", "bic",
]  # fmt: skip
_CUSTOMER_FIELDS = [
    "id", "name", "org_number", "contact_person", "email", "phone", "address", "postal_code",
    "city", "country", "payment_terms_days", "active",
]  # fmt: skip
_SUPPLIER_FIELDS = _CUSTOMER_FIELDS + [
    "payment_type", "bankgiro_number", "plusgiro_number", "clearing_number", "account_number", "iban", "bic",
]  # fmt: skip
_INVOICE_FIELDS = [
    "id", "customer_id", "invoice_number", "invoice_series", "invoice_date", "due_date", "paid_date",
    "reference", "our_reference", "total_amount", "vat_amount", "net_amount", "status", "payment_status",
    "paid_amount", "notes", "message", "invoice_verification_id", "payment_verification_id", "pdf_path",
    "payment_type", "bankgiro_number", "plusgiro_number", "clearing_number", "account_number", "iban", "bic",
    "created_at", "updated_at", "sent_at",
]  # fmt: skip
_SUPPLIER_INVOICE_FIELDS = [
    "id", "supplier_id", "supplier_invoice_number", "our_invoice_number", "invoice_date", "due_date",
    "paid_date", "total_amount", "vat_amount", "net_amount", "status", "payment_status", "paid_amount",
    "ocr_number", "reference", "notes", "invoice_verification_id", "payment_verification_id",
    "created_at", "updated_at",
]  # fmt: skip
_PAYMENT_FIELDS = [
    "id", "payment_date", "amount", "verification_id", "bank_account_id", "reference", "notes", "created_at",
]  # fmt: skip
_EXPENSE_FIELDS = [
    "id", "employee_name", "expense_date", "description", "amount", "vat_amount", "expense_account_id",
    "vat_account_id", "status", "approved_date", "paid_date", "verification_id", "created_at", "updated_at",
]  # fmt: skip


def _payment_row(p: Any) -> fmt.PaymentRow:
    d = _fields(p, _PAYMENT_FIELDS)
    d["bank_account_number"] = p.bank_account.account_number if p.bank_account else None
    return fmt.PaymentRow(**d)


class CompanyExporter:
    """Collects every row belonging to one company."""

    def __init__(self, db: Session, company: Company, user_emails: dict[int, str]):
        self.db = db
        self.company = company
        self.user_emails = user_emails
        self.warnings: list[str] = []
        self.counts: dict[str, int] = {}

    def _email(self, user_id: int | None) -> str | None:
        return self.user_emails.get(user_id) if user_id is not None else None

    def _q(self, model):
        return self.db.query(model).filter(model.company_id == self.company.id)

    def company_row(self) -> fmt.CompanyRow:
        return fmt.CompanyRow(**_fields(self.company, _COMPANY_FIELDS))

    def company_users(self) -> list[fmt.CompanyUserRow]:
        rows = []
        for cu in self._q(CompanyUser).order_by(CompanyUser.id).all():
            email = self._email(cu.user_id)
            if email is None:
                self.warnings.append(f"company_users: user id {cu.user_id} not found, skipped")
                continue
            rows.append(
                fmt.CompanyUserRow(
                    email=email, role=cu.role, created_by_email=self._email(cu.created_by), created_at=cu.created_at
                )
            )
        return rows

    def fiscal_years(self) -> list[fmt.FiscalYearRow]:
        return [
            fmt.FiscalYearRow(**_fields(fy, ["id", "year", "label", "start_date", "end_date", "is_closed"]))
            for fy in self._q(FiscalYear).order_by(FiscalYear.start_date).all()
        ]

    def accounts(self) -> list[fmt.AccountRow]:
        rows = []
        for a in self._q(Account).order_by(Account.fiscal_year_id, Account.account_number).all():
            d = _fields(
                a,
                [
                    "id",
                    "fiscal_year_id",
                    "account_number",
                    "name",
                    "description",
                    "account_type",
                    "opening_balance",
                    "current_balance",
                    "active",
                    "is_bas_account",
                    "sru_code",
                ],  # fmt: skip
            )
            d["fiscal_year_label"] = a.fiscal_year.label
            rows.append(fmt.AccountRow(**d))
        return rows

    def verifications(self) -> list[fmt.VerificationRow]:
        rows = []
        query = self._q(Verification).order_by(
            Verification.fiscal_year_id, Verification.series, Verification.verification_number
        )
        for v in query.all():
            lines = [
                fmt.TransactionLineRow(
                    id=line.id,
                    account_id=line.account_id,
                    account_number=line.account.account_number,
                    debit=line.debit,
                    credit=line.credit,
                    description=line.description,
                )
                for line in sorted(v.transaction_lines, key=lambda x: x.id)
            ]
            d = _fields(
                v,
                [
                    "id",
                    "fiscal_year_id",
                    "series",
                    "verification_number",
                    "transaction_date",
                    "registration_date",
                    "description",
                    "locked",
                    "created_at",
                    "updated_at",
                ],  # fmt: skip
            )
            rows.append(fmt.VerificationRow(**d, lines=lines))
        return rows

    def customers(self) -> list[fmt.CustomerRow]:
        return [fmt.CustomerRow(**_fields(c, _CUSTOMER_FIELDS)) for c in self._q(Customer).order_by(Customer.id).all()]

    def suppliers(self) -> list[fmt.SupplierRow]:
        return [fmt.SupplierRow(**_fields(s, _SUPPLIER_FIELDS)) for s in self._q(Supplier).order_by(Supplier.id).all()]

    def invoices(self) -> list[fmt.InvoiceRow]:
        rows = []
        for inv in self._q(Invoice).order_by(Invoice.id).all():
            lines = []
            for line in sorted(inv.invoice_lines, key=lambda x: x.id):
                d = _fields(
                    line,
                    [
                        "id",
                        "description",
                        "quantity",
                        "unit",
                        "unit_price",
                        "vat_rate",
                        "account_id",
                        "net_amount",
                        "vat_amount",
                        "total_amount",
                    ],  # fmt: skip
                )
                d["account_number"] = line.account.account_number if line.account else None
                lines.append(fmt.InvoiceLineRow(**d))
            payments = [_payment_row(p) for p in sorted(inv.payments, key=lambda x: x.id)]
            rows.append(fmt.InvoiceRow(**_fields(inv, _INVOICE_FIELDS), lines=lines, payments=payments))
        return rows

    def supplier_invoices(self) -> list[fmt.SupplierInvoiceRow]:
        rows = []
        for inv in self._q(SupplierInvoice).order_by(SupplierInvoice.id).all():
            lines = []
            for line in sorted(inv.supplier_invoice_lines, key=lambda x: x.id):
                d = _fields(
                    line,
                    [
                        "id",
                        "description",
                        "quantity",
                        "unit_price",
                        "vat_rate",
                        "account_id",
                        "net_amount",
                        "vat_amount",
                        "total_amount",
                    ],  # fmt: skip
                )
                d["account_number"] = line.account.account_number if line.account else None
                lines.append(fmt.SupplierInvoiceLineRow(**d))
            payments = [_payment_row(p) for p in sorted(inv.payments, key=lambda x: x.id)]
            rows.append(
                fmt.SupplierInvoiceRow(**_fields(inv, _SUPPLIER_INVOICE_FIELDS), lines=lines, payments=payments)
            )
        return rows

    def expenses(self) -> list[fmt.ExpenseRow]:
        return [fmt.ExpenseRow(**_fields(e, _EXPENSE_FIELDS)) for e in self._q(Expense).order_by(Expense.id).all()]

    def posting_templates(self) -> list[fmt.PostingTemplateRow]:
        rows = []
        for t in self._q(PostingTemplate).order_by(PostingTemplate.id).all():
            lines = [
                fmt.PostingTemplateLineRow(
                    **_fields(line, ["id", "account_number", "formula", "description", "sort_order"])
                )
                for line in sorted(t.template_lines, key=lambda x: (x.sort_order, x.id))
            ]
            d = _fields(
                t,
                [
                    "id",
                    "name",
                    "description",
                    "default_series",
                    "default_journal_text",
                    "sort_order",
                    "created_at",
                    "updated_at",
                ],
            )
            rows.append(fmt.PostingTemplateRow(**d, lines=lines))
        return rows

    def default_accounts(self) -> list[fmt.DefaultAccountRow]:
        return [
            fmt.DefaultAccountRow(
                id=d.id, account_type=d.account_type, account_id=d.account_id, account_number=d.account.account_number
            )
            for d in self._q(DefaultAccount).order_by(DefaultAccount.id).all()
        ]

    def attachments(self) -> list[fmt.AttachmentRow]:
        rows = []
        for a in self._q(Attachment).order_by(Attachment.id).all():
            links = [
                fmt.AttachmentLinkRow(
                    entity_type=_val(link.entity_type),
                    entity_id=link.entity_id,
                    role=_val(link.role),
                    sort_order=link.sort_order,
                    created_at=link.created_at,
                )
                for link in sorted(a.links, key=lambda x: x.id)
            ]
            d = _fields(
                a,
                [
                    "id",
                    "original_filename",
                    "storage_filename",
                    "mime_type",
                    "size_bytes",
                    "checksum_sha256",
                    "status",
                    "rejection_reason",
                    "created_at",
                ],  # fmt: skip
            )
            rows.append(fmt.AttachmentRow(**d, created_by_email=self._email(a.created_by), links=links))
        return rows

    def chat_sessions(self) -> list[fmt.ChatSessionRow]:
        rows = []
        for s in self._q(ChatSession).order_by(ChatSession.id).all():
            messages = [
                fmt.ChatMessageRow(
                    **_fields(
                        m,
                        [
                            "id",
                            "role",
                            "content",
                            "tool_name",
                            "tool_args",
                            "tool_status",
                            "attachment_ids",
                            "created_at",
                        ],
                    )
                )
                for m in sorted(s.messages, key=lambda x: x.id)
            ]
            rows.append(
                fmt.ChatSessionRow(
                    id=s.id,
                    user_email=self._email(s.user_id),
                    title=s.title,
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                    messages=messages,
                )
            )
        return rows

    def ai_uploads(self) -> list[fmt.AIUploadRow]:
        return [
            fmt.AIUploadRow(
                **_fields(u, ["id", "original_filename", "storage_filename", "mime_type", "size_bytes", "created_at"]),
                created_by_email=self._email(u.created_by),
            )
            for u in self._q(AIUpload).order_by(AIUpload.id).all()
        ]


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def export_archive(
    db: Session,
    out_path: Path,
    *,
    scope: str = "instance",
    company_ids: list[int] | None = None,
    uploads_dir: Path = UPLOADS_DIR,
    include_ai: bool = True,
    include_credentials: bool | None = None,
) -> fmt.Manifest:
    """Write a portable archive to ``out_path`` and return its manifest.

    scope="instance": every company plus users and instance settings (a full backup).
    scope="company":  only the companies in ``company_ids``, no users, no credentials.
    """
    if scope not in ("instance", "company"):
        raise ValueError(f"Unknown scope: {scope}")
    if include_credentials is None:
        include_credentials = scope == "instance"
    if scope == "company" and not company_ids:
        raise ValueError("company scope requires company_ids")

    users = db.query(User).order_by(User.id).all()
    user_emails = {u.id: u.email for u in users}

    query = db.query(Company).order_by(Company.id)
    if company_ids:
        query = query.filter(Company.id.in_(company_ids))
    companies = query.all()
    if company_ids and len(companies) != len(set(company_ids)):
        raise ValueError("One or more company ids do not exist")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = _ZipWriter(out_path)
    warnings: list[str] = []
    counts: dict[str, int] = {"companies": len(companies), "files": 0}
    entries: list[fmt.CompanyEntry] = []
    written_files: set[str] = set()

    def add_file(subdir: str, filename: str, label: str) -> None:
        member = f"files/{subdir}/{filename}"
        if member in written_files:
            return
        source = uploads_dir / subdir / filename
        if not source.is_file():
            warnings.append(f"{label}: file missing on disk: {subdir}/{filename}")
            return
        writer.write_file(member, source)
        written_files.add(member)
        counts["files"] += 1

    try:
        # schema/ — the format, machine readable
        for name, model in fmt.SCHEMA_MODELS.items():
            writer.write_text(f"schema/{name}.schema.json", json.dumps(model.model_json_schema(), indent=2) + "\n")

        # instance/
        if scope == "instance":
            user_rows = [
                fmt.UserRow(
                    id=u.id,
                    email=u.email,
                    full_name=u.full_name,
                    is_admin=u.is_admin,
                    is_active=u.is_active,
                    hashed_password=u.hashed_password if include_credentials else None,
                    is_service_account=bool(getattr(u, "is_service_account", False)),
                    owner_email=user_emails.get(getattr(u, "owner_id", None)),
                    api_key_hash=(getattr(u, "api_key_hash", None) if include_credentials else None),
                    created_at=u.created_at,
                    updated_at=u.updated_at,
                )
                for u in users
            ]
            writer.write_json("instance/users.json", user_rows)
            counts["users"] = len(user_rows)

            ai = db.query(AISettings).order_by(AISettings.id).first()
            sched = db.query(BackupSchedule).order_by(BackupSchedule.id).first()
            settings_row = fmt.InstanceSettings(
                ai_settings=(
                    fmt.AISettingsRow(
                        ai_enabled=ai.ai_enabled,
                        ollama_url=ai.ollama_url,
                        ollama_model=ai.ollama_model,
                        system_prompt=ai.system_prompt,
                    )
                    if ai
                    else None
                ),
                backup_schedule=(
                    fmt.BackupScheduleRow(
                        enabled=sched.enabled,
                        interval_hours=sched.interval_hours,
                        max_backups=sched.max_backups,
                        preferred_time=(sched.preferred_time.strftime("%H:%M") if sched.preferred_time else "03:00"),
                    )
                    if sched
                    else None
                ),
            )
            writer.write_text("instance/settings.json", settings_row.model_dump_json(indent=2) + "\n")

        # companies/
        for company in companies:
            base = f"companies/{_company_dirname(company.org_number)}"
            exp = CompanyExporter(db, company, user_emails)
            entries.append(fmt.CompanyEntry(org_number=company.org_number, name=company.name, path=base))

            writer.write_text(f"{base}/company.json", exp.company_row().model_dump_json(indent=2) + "\n")
            writer.write_json(f"{base}/company_users.json", exp.company_users())
            fiscal_years = exp.fiscal_years()
            writer.write_json(f"{base}/fiscal_years.json", fiscal_years)

            tables: list[tuple[str, str, list]] = [
                ("accounts", "jsonl", exp.accounts()),
                ("verifications", "jsonl", exp.verifications()),
                ("customers", "json", exp.customers()),
                ("suppliers", "json", exp.suppliers()),
                ("invoices", "jsonl", exp.invoices()),
                ("supplier_invoices", "jsonl", exp.supplier_invoices()),
                ("expenses", "jsonl", exp.expenses()),
                ("posting_templates", "json", exp.posting_templates()),
                ("default_accounts", "json", exp.default_accounts()),
                ("attachments", "jsonl", exp.attachments()),
            ]
            for name, kind, rows in tables:
                (writer.write_jsonl if kind == "jsonl" else writer.write_json)(f"{base}/{name}.{kind}", rows)
                counts[name] = counts.get(name, 0) + len(rows)

            for att in next(rows for name, _, rows in tables if name == "attachments"):
                add_file(ATTACHMENTS_SUBDIR, att.storage_filename, f"{company.org_number} attachment {att.id}")

            if company.logo_filename:
                add_file(LOGOS_SUBDIR, company.logo_filename, f"{company.org_number} logo")

            if include_ai:
                sessions = exp.chat_sessions()
                uploads = exp.ai_uploads()
                writer.write_jsonl(f"{base}/ai/chat_sessions.jsonl", sessions)
                writer.write_jsonl(f"{base}/ai/uploads.jsonl", uploads)
                counts["chat_sessions"] = counts.get("chat_sessions", 0) + len(sessions)
                counts["ai_uploads"] = counts.get("ai_uploads", 0) + len(uploads)
                for up in uploads:
                    add_file(AI_UPLOADS_SUBDIR, up.storage_filename, f"{company.org_number} ai upload {up.id}")

            for fy in fiscal_years:
                try:
                    sie = export_sie4(db, company.id, fy.id)
                except Exception as e:  # pragma: no cover - defensive
                    warnings.append(f"{company.org_number}: SIE export for {fy.label} failed: {e}")
                    continue
                writer.write_text(f"{base}/sie/{_company_dirname(fy.label)}.se", sie + "\n")

            warnings.extend(exp.warnings)

        manifest = fmt.Manifest(
            scope=scope,
            created_at=datetime.now(UTC),
            app_version=__version__,
            schema_version=_schema_version(db),
            includes_credentials=include_credentials,
            includes_ai=include_ai,
            companies=entries,
            counts=counts,
            warnings=warnings,
            files=writer.entries,
        )
        writer.zip.writestr("manifest.json", manifest.model_dump_json(indent=2) + "\n")
    finally:
        writer.close()

    for w in warnings:
        logger.warning(f"archive export: {w}")
    logger.info(f"Archive written: {out_path} ({counts})")
    return manifest
