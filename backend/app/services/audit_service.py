"""Audit log: every insert, update and delete on bookkeeping tables is recorded
with who did it, from SQLAlchemy mapper events, inside the same transaction.

The acting user is taken from a context variable that the auth dependency sets
per request. Bulk operations (archive import, restore, seeding) run inside
``suppressed()`` and write one summary entry instead.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.company import Company
from app.models.compliance import AuditLog, PeriodLock, VerificationGapExplanation
from app.models.customer import Customer, Supplier
from app.models.default_account import DefaultAccount
from app.models.expense import Expense
from app.models.fiscal_year import FiscalYear
from app.models.invoice import Invoice, InvoicePayment, SupplierInvoice, SupplierInvoicePayment
from app.models.posting_template import PostingTemplate
from app.models.user import CompanyUser, User
from app.models.verification import Verification

logger = logging.getLogger(__name__)

current_user_email: ContextVar[str | None] = ContextVar("audit_user_email", default=None)
_suppressed: ContextVar[bool] = ContextVar("audit_suppressed", default=False)

IGNORED_ATTRS = {"updated_at", "created_at", "current_balance", "hashed_password", "api_key_hash", "pdf_path"}

TRACKED = (
    Verification,
    Invoice,
    InvoicePayment,
    SupplierInvoice,
    SupplierInvoicePayment,
    Expense,
    Account,
    Customer,
    Supplier,
    Company,
    FiscalYear,
    PostingTemplate,
    DefaultAccount,
    PeriodLock,
    VerificationGapExplanation,
    User,
    CompanyUser,
)


@contextmanager
def suppressed():
    token = _suppressed.set(True)
    try:
        yield
    finally:
        _suppressed.reset(token)


def _json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    if hasattr(value, "value"):  # enum
        return value.value
    return value


def _label(target) -> str:
    if isinstance(target, Verification):
        return f"{target.series}{target.verification_number}"
    if isinstance(target, Invoice):
        return f"{target.invoice_series}{target.invoice_number}"
    if isinstance(target, SupplierInvoice):
        return f"leverantörsfaktura {target.supplier_invoice_number}"
    if isinstance(target, Account):
        return f"{target.account_number} {target.name}"
    if isinstance(target, FiscalYear):
        return target.label
    if isinstance(target, PeriodLock):
        return f"låst t.o.m. {target.locked_through}"
    if isinstance(target, VerificationGapExplanation):
        return f"{target.series}{target.verification_number}"
    if isinstance(target, User | CompanyUser):
        return getattr(target, "email", None) or f"user {getattr(target, 'user_id', '')}"
    name = (
        getattr(target, "name", None) or getattr(target, "description", None) or getattr(target, "employee_name", None)
    )
    return str(name)[:80] if name else f"#{getattr(target, 'id', '?')}"


def _company_id(target) -> int | None:
    if isinstance(target, Company):
        return target.id
    return getattr(target, "company_id", None)


def _write(connection, target, action: str, changes: dict | None) -> None:
    if _suppressed.get():
        return
    connection.execute(
        AuditLog.__table__.insert().values(
            company_id=_company_id(target),
            user_email=current_user_email.get(),
            action=action,
            table_name=target.__tablename__,
            record_id=getattr(target, "id", None),
            summary=f"{action} {target.__tablename__} {_label(target)}",
            changes=json.dumps(changes, ensure_ascii=False) if changes else None,
            created_at=datetime.utcnow(),
        )
    )


def _after_insert(mapper, connection, target):
    _write(connection, target, "insert", None)


def _after_update(mapper, connection, target):
    changes = {}
    for attr in inspect(target).attrs:
        if attr.key in IGNORED_ATTRS or attr.key.startswith("_"):
            continue
        history = attr.history
        if not history.has_changes():
            continue
        old = history.deleted[0] if history.deleted else None
        new = history.added[0] if history.added else None
        if isinstance(old, list | set | dict) or isinstance(new, list | set | dict):
            continue  # relationship collections
        if hasattr(old, "__tablename__") or hasattr(new, "__tablename__"):
            continue  # relationship objects
        changes[attr.key] = [_json_value(old), _json_value(new)]
    if changes:
        _write(connection, target, "update", changes)


def _after_delete(mapper, connection, target):
    _write(connection, target, "delete", None)


_installed = False


def install() -> None:
    global _installed
    if _installed:
        return
    for model in TRACKED:
        event.listen(model, "after_insert", _after_insert)
        event.listen(model, "after_update", _after_update)
        event.listen(model, "after_delete", _after_delete)
    _installed = True


def note(
    db: Session, *, company_id: int | None, summary: str, table_name: str = "system", record_id: int | None = None
) -> None:
    """Write a free-text entry (used for imports, restores and other bulk actions)."""
    db.add(
        AuditLog(
            company_id=company_id,
            user_email=current_user_email.get(),
            action="note",
            table_name=table_name,
            record_id=record_id,
            summary=summary,
            created_at=datetime.utcnow(),
        )
    )


install()
