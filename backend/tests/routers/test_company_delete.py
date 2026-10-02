"""Deleting a company must remove every dependent row, including the ones the
ORM cascades do not reach (invoice lines and payments referencing accounts,
attachments and their links, transaction lines)."""

from datetime import date
from decimal import Decimal

from app.models.account import Account, AccountType
from app.models.attachment import Attachment, AttachmentLink, AttachmentRole, AttachmentStatus, EntityType
from app.models.company import Company
from app.models.invoice import InvoiceStatus, PaymentStatus, SupplierInvoice, SupplierInvoiceLine
from app.models.verification import TransactionLine, Verification
from app.services import storage


def test_delete_company_removes_dependent_rows_and_files(
    client, auth_headers, db_session, test_company_with_fiscal_year, test_supplier, test_user, tmp_path, monkeypatch
):
    company, fy = test_company_with_fiscal_year
    monkeypatch.setattr(storage, "ATTACHMENTS_DIR", tmp_path)
    from app.services import attachment_service

    monkeypatch.setattr(attachment_service, "ATTACHMENTS_DIR", tmp_path)

    cost = Account(
        company_id=company.id,
        fiscal_year_id=fy.id,
        account_number=6110,
        name="Kontor",
        account_type=AccountType.COST_OTHER,
    )
    bank = Account(
        company_id=company.id, fiscal_year_id=fy.id, account_number=1930, name="Bank", account_type=AccountType.ASSET
    )
    db_session.add_all([cost, bank])
    db_session.flush()
    ver = Verification(
        company_id=company.id,
        fiscal_year_id=fy.id,
        verification_number=1,
        series="A",
        transaction_date=date(2025, 1, 2),
        description="x",
    )
    db_session.add(ver)
    db_session.flush()
    db_session.add_all(
        [
            TransactionLine(verification_id=ver.id, account_id=cost.id, debit=Decimal("100"), credit=0),
            TransactionLine(verification_id=ver.id, account_id=bank.id, debit=0, credit=Decimal("100")),
        ]
    )
    sinv = SupplierInvoice(
        company_id=company.id,
        supplier_id=test_supplier.id,
        supplier_invoice_number="L1",
        invoice_date=date(2025, 1, 2),
        due_date=date(2025, 2, 1),
        total_amount=Decimal("100"),
        vat_amount=0,
        net_amount=Decimal("100"),
        status=InvoiceStatus.DRAFT,
        payment_status=PaymentStatus.UNPAID,
        paid_amount=0,
    )
    db_session.add(sinv)
    db_session.flush()
    db_session.add(
        SupplierInvoiceLine(
            supplier_invoice_id=sinv.id,
            description="x",
            quantity=1,
            unit_price=Decimal("100"),
            vat_rate=0,
            account_id=cost.id,
            net_amount=Decimal("100"),
            vat_amount=0,
            total_amount=Decimal("100"),
        )
    )
    (tmp_path / "r.pdf").write_bytes(b"%PDF")
    att = Attachment(
        company_id=company.id,
        original_filename="r.pdf",
        storage_filename="r.pdf",
        mime_type="application/pdf",
        size_bytes=4,
        status=AttachmentStatus.READY,
        created_by=test_user.id,
    )
    db_session.add(att)
    db_session.flush()
    db_session.add(
        AttachmentLink(
            attachment_id=att.id, entity_type=EntityType.VERIFICATION, entity_id=ver.id, role=AttachmentRole.ORIGINAL
        )
    )
    db_session.commit()
    company_id = company.id

    response = client.delete(f"/api/companies/{company_id}", headers=auth_headers)
    assert response.status_code == 204, response.text

    db_session.expire_all()
    assert db_session.query(Company).filter(Company.id == company_id).count() == 0
    for model in (
        Account,
        Verification,
        TransactionLine,
        SupplierInvoice,
        SupplierInvoiceLine,
        Attachment,
        AttachmentLink,
    ):
        assert db_session.query(model).count() == 0, model.__name__
    assert not (tmp_path / "r.pdf").exists()
