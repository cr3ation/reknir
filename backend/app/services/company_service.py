"""Company-level operations that span many tables."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.ai_assistant import AIUpload, ChatMessage, ChatSession
from app.models.attachment import Attachment, AttachmentLink
from app.models.company import Company
from app.models.customer import Customer, Supplier
from app.models.default_account import DefaultAccount
from app.models.expense import Expense
from app.models.fiscal_year import FiscalYear
from app.models.invitation import Invitation
from app.models.invoice import (
    Invoice,
    InvoiceLine,
    InvoicePayment,
    SupplierInvoice,
    SupplierInvoiceLine,
    SupplierInvoicePayment,
)
from app.models.posting_template import PostingTemplate, PostingTemplateLine
from app.models.user import CompanyUser
from app.models.verification import TransactionLine, Verification
from app.services import attachment_service
from app.services.storage import AI_UPLOADS_DIR, LOGOS_DIR

logger = logging.getLogger(__name__)


def delete_company(db: Session, company: Company) -> dict[str, int]:
    """Delete a company and everything that belongs to it, in dependency order.

    The ORM cascades on Company do not cover rows that reference accounts and
    verifications from other tables (invoice lines, payments, attachments, ...),
    so the deletes are issued explicitly here. Files on disk are removed after
    the database rows. Does not commit.
    """
    cid = company.id
    counts: dict[str, int] = {}

    def wipe(model, condition) -> None:
        counts[model.__tablename__] = db.query(model).filter(condition).delete(synchronize_session=False)

    sub = lambda model: db.query(model.id).filter(model.company_id == cid)  # noqa: E731

    # Files to remove once the transaction has been committed by the caller
    storage_names = [s for (s,) in db.query(Attachment.storage_filename).filter(Attachment.company_id == cid)]
    ai_names = [s for (s,) in db.query(AIUpload.storage_filename).filter(AIUpload.company_id == cid)]
    logo = company.logo_filename

    wipe(SupplierInvoicePayment, SupplierInvoicePayment.supplier_invoice_id.in_(sub(SupplierInvoice)))
    wipe(SupplierInvoiceLine, SupplierInvoiceLine.supplier_invoice_id.in_(sub(SupplierInvoice)))
    wipe(SupplierInvoice, SupplierInvoice.company_id == cid)
    wipe(InvoicePayment, InvoicePayment.invoice_id.in_(sub(Invoice)))
    wipe(InvoiceLine, InvoiceLine.invoice_id.in_(sub(Invoice)))
    wipe(Invoice, Invoice.company_id == cid)
    wipe(Expense, Expense.company_id == cid)
    wipe(AttachmentLink, AttachmentLink.attachment_id.in_(sub(Attachment)))
    wipe(Attachment, Attachment.company_id == cid)
    wipe(TransactionLine, TransactionLine.verification_id.in_(sub(Verification)))
    wipe(Verification, Verification.company_id == cid)
    wipe(DefaultAccount, DefaultAccount.company_id == cid)
    wipe(PostingTemplateLine, PostingTemplateLine.template_id.in_(sub(PostingTemplate)))
    wipe(PostingTemplate, PostingTemplate.company_id == cid)
    wipe(ChatMessage, ChatMessage.session_id.in_(sub(ChatSession)))
    wipe(ChatSession, ChatSession.company_id == cid)
    wipe(AIUpload, AIUpload.company_id == cid)
    wipe(Invitation, Invitation.company_id == cid)
    wipe(CompanyUser, CompanyUser.company_id == cid)
    wipe(Account, Account.company_id == cid)
    wipe(FiscalYear, FiscalYear.company_id == cid)
    wipe(Customer, Customer.company_id == cid)
    wipe(Supplier, Supplier.company_id == cid)
    db.query(Company).filter(Company.id == cid).delete(synchronize_session=False)
    db.flush()

    for name in storage_names:
        attachment_service.delete_file(name)
    for name in ai_names:
        path = AI_UPLOADS_DIR / name
        if path.exists():
            path.unlink()
    if logo and (LOGOS_DIR / logo).exists():
        (LOGOS_DIR / logo).unlink()

    logger.info(f"Deleted company {cid} ({company.name}): {counts}")
    return counts
