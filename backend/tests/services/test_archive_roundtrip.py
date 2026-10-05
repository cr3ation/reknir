"""Round-trip test for the portable JSON + files archive.

seed -> export -> verify -> import into an empty database -> export again ->
the two archives must describe the same data (ids and file order aside).
"""

import hashlib
import json
import zipfile
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.account import Account, AccountType
from app.models.ai_assistant import AISettings, AIUpload, ChatMessage, ChatSession
from app.models.attachment import Attachment, AttachmentLink, AttachmentRole, AttachmentStatus, EntityType
from app.models.backup_schedule import BackupSchedule
from app.models.company import Company
from app.models.compliance import AuditLog, PeriodLock, VerificationGapExplanation
from app.models.default_account import DefaultAccount
from app.models.expense import Expense, ExpenseStatus
from app.models.fiscal_year import FiscalYear
from app.models.invoice import (
    Invoice,
    InvoiceLine,
    InvoicePayment,
    InvoiceStatus,
    PaymentStatus,
    SupplierInvoice,
    SupplierInvoiceLine,
)
from app.models.posting_template import PostingTemplate, PostingTemplateLine
from app.models.user import User
from app.models.verification import TransactionLine, Verification
from app.services import archive_export_service as export_svc
from app.services import archive_import_service as import_svc

ID_KEYS = {"id"}


def _write(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _account(accounts: list[Account], number: int) -> Account:
    return next(a for a in accounts if a.account_number == number)


@pytest.fixture
def seeded(db_session, test_company_with_fiscal_year, test_customer, test_supplier, test_user, tmp_path):
    """A company with one of everything, plus files on disk under tmp_path/uploads."""
    company, fy = test_company_with_fiscal_year
    uploads = tmp_path / "uploads"
    accounts = [
        Account(
            company_id=company.id,
            fiscal_year_id=fy.id,
            account_number=n,
            name=name,
            account_type=kind,
            opening_balance=ib,
        )
        for n, name, kind, ib in [
            (1510, "Kundfordringar", AccountType.ASSET, Decimal("0")),
            (1930, "Företagskonto", AccountType.ASSET, Decimal("50000.00")),
            (2611, "Utgående moms 25%", AccountType.EQUITY_LIABILITY, Decimal("0")),
            (2641, "Ingående moms", AccountType.EQUITY_LIABILITY, Decimal("0")),
            (3001, "Försäljning 25%", AccountType.REVENUE, Decimal("0")),
            (6110, "Kontorsmaterial", AccountType.COST_OTHER, Decimal("0")),
        ]
    ]
    db_session.add_all(accounts)
    db_session.flush()
    bank = _account(accounts, 1930)
    receivable = _account(accounts, 1510)
    revenue = _account(accounts, 3001)
    vat_out = _account(accounts, 2611)
    cost = _account(accounts, 6110)
    bank.current_balance = Decimal("51250.00")
    receivable.current_balance = Decimal("0")
    revenue.current_balance = Decimal("-1000.00")
    vat_out.current_balance = Decimal("-250.00")

    ver = Verification(
        company_id=company.id,
        fiscal_year_id=fy.id,
        verification_number=1,
        series="A",
        transaction_date=date(2025, 3, 4),
        registration_date=date(2025, 3, 5),
        description="Faktura F1",
        locked=True,
    )
    db_session.add(ver)
    db_session.flush()
    db_session.add_all(
        [
            TransactionLine(verification_id=ver.id, account_id=receivable.id, debit=Decimal("1250.00"), credit=0),
            TransactionLine(verification_id=ver.id, account_id=revenue.id, debit=0, credit=Decimal("1000.00")),
            TransactionLine(
                verification_id=ver.id, account_id=vat_out.id, debit=0, credit=Decimal("250.00"), description="Moms"
            ),
        ]
    )
    pay_ver = Verification(
        company_id=company.id,
        fiscal_year_id=fy.id,
        verification_number=2,
        series="A",
        transaction_date=date(2025, 3, 20),
        registration_date=date(2025, 3, 20),
        description="Betalning F1",
    )
    db_session.add(pay_ver)
    db_session.flush()
    db_session.add_all(
        [
            TransactionLine(verification_id=pay_ver.id, account_id=bank.id, debit=Decimal("1250.00"), credit=0),
            TransactionLine(verification_id=pay_ver.id, account_id=receivable.id, debit=0, credit=Decimal("1250.00")),
        ]
    )

    invoice = Invoice(
        company_id=company.id,
        customer_id=test_customer.id,
        invoice_number=1,
        invoice_series="F",
        invoice_date=date(2025, 3, 4),
        due_date=date(2025, 4, 3),
        paid_date=date(2025, 3, 20),
        reference="Kund ref",
        total_amount=Decimal("1250.00"),
        vat_amount=Decimal("250.00"),
        net_amount=Decimal("1000.00"),
        status=InvoiceStatus.ISSUED,
        payment_status=PaymentStatus.PAID,
        paid_amount=Decimal("1250.00"),
        invoice_verification_id=ver.id,
        payment_verification_id=pay_ver.id,
        sent_at=datetime(2025, 3, 4, 9, 30),
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(
        InvoiceLine(
            invoice_id=invoice.id,
            description="Konsulttimmar",
            quantity=Decimal("10"),
            unit="tim",
            unit_price=Decimal("100.00"),
            vat_rate=Decimal("25.00"),
            account_id=revenue.id,
            net_amount=Decimal("1000.00"),
            vat_amount=Decimal("250.00"),
            total_amount=Decimal("1250.00"),
        )
    )
    db_session.add(
        InvoicePayment(
            invoice_id=invoice.id,
            payment_date=date(2025, 3, 20),
            amount=Decimal("1250.00"),
            verification_id=pay_ver.id,
            bank_account_id=bank.id,
            reference="OCR 123",
        )
    )

    sinv = SupplierInvoice(
        company_id=company.id,
        supplier_id=test_supplier.id,
        supplier_invoice_number="LEV-77",
        our_invoice_number=1,
        invoice_date=date(2025, 5, 1),
        due_date=date(2025, 5, 31),
        total_amount=Decimal("500.00"),
        vat_amount=Decimal("100.00"),
        net_amount=Decimal("400.00"),
        status=InvoiceStatus.DRAFT,
        payment_status=PaymentStatus.UNPAID,
        paid_amount=0,
        ocr_number="1234567890",
    )
    db_session.add(sinv)
    db_session.flush()
    db_session.add(
        SupplierInvoiceLine(
            supplier_invoice_id=sinv.id,
            description="Kontorsmaterial",
            quantity=1,
            unit_price=Decimal("400.00"),
            vat_rate=Decimal("25.00"),
            account_id=cost.id,
            net_amount=Decimal("400.00"),
            vat_amount=Decimal("100.00"),
            total_amount=Decimal("500.00"),
        )
    )

    expense = Expense(
        company_id=company.id,
        employee_name="Anna",
        expense_date=date(2025, 6, 2),
        description="Tågbiljett",
        amount=Decimal("300.00"),
        vat_amount=Decimal("18.00"),
        expense_account_id=cost.id,
        vat_account_id=vat_out.id,
        status=ExpenseStatus.SUBMITTED,
    )
    db_session.add(expense)

    template = PostingTemplate(company_id=company.id, name="Inköp 25%", description="Inköp med moms", sort_order=1)
    db_session.add(template)
    db_session.flush()
    db_session.add_all(
        [
            PostingTemplateLine(template_id=template.id, account_number=1930, formula="-{total}", sort_order=0),
            PostingTemplateLine(template_id=template.id, account_number=2641, formula="{total}*0.2", sort_order=1),
            PostingTemplateLine(template_id=template.id, account_number=6110, formula="{total}*0.8", sort_order=2),
        ]
    )
    db_session.add(DefaultAccount(company_id=company.id, account_type="bank", account_id=bank.id))

    receipt = b"%PDF-1.4 fake receipt"
    receipt_sha = _write(uploads / "attachments" / "aaaa-receipt.pdf", receipt)
    att = Attachment(
        company_id=company.id,
        original_filename="kvitto.pdf",
        storage_filename="aaaa-receipt.pdf",
        mime_type="application/pdf",
        size_bytes=len(receipt),
        checksum_sha256=receipt_sha,
        status=AttachmentStatus.READY,
        created_by=test_user.id,
    )
    db_session.add(att)
    db_session.flush()
    db_session.add_all(
        [
            AttachmentLink(
                attachment_id=att.id,
                entity_type=EntityType.VERIFICATION,
                entity_id=ver.id,
                role=AttachmentRole.ORIGINAL,
            ),
            AttachmentLink(
                attachment_id=att.id,
                entity_type=EntityType.INVOICE,
                entity_id=invoice.id,
                role=AttachmentRole.ARCHIVED_PDF,
            ),
        ]
    )
    unlinked = b"unlinked"
    db_session.add(
        Attachment(
            company_id=company.id,
            original_filename="lös.png",
            storage_filename="bbbb-unlinked.png",
            mime_type="image/png",
            size_bytes=len(unlinked),
            checksum_sha256=_write(uploads / "attachments" / "bbbb-unlinked.png", unlinked),
            status=AttachmentStatus.UPLOADED,
            created_by=test_user.id,
        )
    )

    _write(uploads / "logos" / "logo.png", b"PNG logo")
    company.logo_filename = "logo.png"

    session = ChatSession(
        company_id=company.id,
        user_id=test_user.id,
        title="Fråga om moms",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(session)
    db_session.flush()
    db_session.add(
        ChatMessage(session_id=session.id, role="user", content="Hur bokför jag moms?", created_at=datetime.now(UTC))
    )
    _write(uploads / "ai_uploads" / "cccc-scan.png", b"scan")
    db_session.add(
        AIUpload(
            company_id=company.id,
            original_filename="scan.png",
            storage_filename="cccc-scan.png",
            mime_type="image/png",
            size_bytes=4,
            created_at=datetime.now(UTC),
            created_by=test_user.id,
        )
    )
    db_session.add(
        AISettings(
            id=1,
            ai_enabled=True,
            ollama_url="http://ollama:11434",
            ollama_model="gemma4:latest",
            system_prompt="Var kort.",
        )
    )
    db_session.add(BackupSchedule(id=1, enabled=True, interval_hours=24, max_backups=14))
    # compliance data: a reversal link, a period lock, a gap explanation and audit entries
    pay_ver.reverses_verification_id = ver.id
    ver.reversed_by_verification_id = pay_ver.id
    db_session.add(
        PeriodLock(company_id=company.id, locked_through=date(2025, 3, 31), note="Moms Q1", created_by=test_user.id)
    )
    db_session.add(
        VerificationGapExplanation(
            company_id=company.id,
            fiscal_year_id=fy.id,
            series="A",
            verification_number=3,
            explanation="Makulerad",
            created_by=test_user.id,
        )
    )
    db_session.add(
        AuditLog(
            company_id=company.id,
            user_email=test_user.email,
            action="insert",
            table_name="verifications",
            record_id=ver.id,
            summary="insert verifications A1",
            changes=None,
            created_at=datetime(2025, 3, 4, 10, 0),
        )
    )
    db_session.add(
        AuditLog(
            company_id=None,
            user_email=test_user.email,
            action="note",
            table_name="system",
            record_id=None,
            summary="restore from backup",
            changes=None,
            created_at=datetime(2025, 3, 5, 10, 0),
        )
    )
    db_session.add(
        User(
            email="mcp-bot@service.local",
            full_name="MCP Bot",
            is_admin=False,
            hashed_password="!",
            is_service_account=True,
            owner_id=test_user.id,
            api_key_hash="sha256:deadbeef",
        )
    )
    db_session.commit()
    return company, uploads


def _fresh_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _strip_ids(value):
    if isinstance(value, dict):
        return {k: _strip_ids(v) for k, v in value.items() if k not in ID_KEYS and not k.endswith("_id")}
    if isinstance(value, list):
        return [_strip_ids(v) for v in value]
    return value


def _data_members(zip_path: Path) -> dict[str, object]:
    """Every data file in the archive, parsed, with ids removed."""
    out = {}
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.endswith("audit_log.jsonl"):
                continue  # the import itself adds history entries, so this file legitimately grows
            if name.startswith(("companies/", "instance/")) and name.endswith((".json", ".jsonl")):
                text = zf.read(name).decode()
                if name.endswith(".jsonl"):
                    parsed = [json.loads(line) for line in text.splitlines() if line.strip()]
                else:
                    parsed = json.loads(text)
                out[name] = _strip_ids(parsed)
            elif name.startswith("companies/") and name.endswith(".se"):
                out[name] = [line for line in zf.read(name).decode().splitlines() if not line.startswith("#GEN")]
    return out


def test_export_verify_import_roundtrip(db_session, seeded, tmp_path, test_user):
    company, uploads = seeded
    first = tmp_path / "first.zip"
    manifest = export_svc.export_archive(db_session, first, scope="instance", uploads_dir=uploads)

    assert manifest.scope == "instance"
    assert manifest.includes_credentials is True
    assert manifest.warnings == []
    assert manifest.counts["companies"] == 1
    assert manifest.counts["files"] == 4  # 2 attachments + logo + ai upload
    with zipfile.ZipFile(first) as zf:
        names = set(zf.namelist())
    base = manifest.companies[0].path
    for expected in (
        "manifest.json",
        "schema/verification.schema.json",
        "instance/users.json",
        "instance/settings.json",
        f"{base}/company.json",
        f"{base}/verifications.jsonl",
        f"{base}/attachments.jsonl",
        f"{base}/ai/chat_sessions.jsonl",
        "files/attachments/aaaa-receipt.pdf",
        "files/attachments/bbbb-unlinked.png",
        "files/logos/logo.png",
        "files/ai_uploads/cccc-scan.png",
    ):
        assert expected in names, expected
    assert any(n.startswith(f"{base}/sie/") and n.endswith(".se") for n in names)

    archive = import_svc.verify_archive(first)
    assert len(archive.users) == 2
    assert archive.users[0].hashed_password
    bot = next(u for u in archive.users if u.is_service_account)
    assert bot.owner_email == "testuser@example.com" and bot.api_key_hash == "sha256:deadbeef"
    assert (
        archive.settings
        and archive.settings.ai_settings
        and archive.settings.ai_settings.ollama_model == "gemma4:latest"
    )
    data = archive.companies[0]
    assert len(data.verifications) == 2
    assert data.verifications[0].lines[2].description == "Moms"
    assert data.invoices[0].payments[0].bank_account_number == 1930
    assert data.attachments[0].links[1].role == "archived_pdf"

    # Import into an empty database and a fresh uploads directory
    target = _fresh_session()
    uploads2 = tmp_path / "uploads2"
    report = import_svc.load_archive(target, archive, uploads_target=uploads2, import_users=True)
    target.commit()
    assert report.warnings == []
    assert report.created["verifications"] == 2
    assert report.created["attachments"] == 2
    assert report.created["users"] == 2
    assert (uploads2 / "attachments" / "aaaa-receipt.pdf").read_bytes() == b"%PDF-1.4 fake receipt"
    assert (uploads2 / "logos" / "logo.png").exists()
    assert (uploads2 / "ai_uploads" / "cccc-scan.png").exists()

    import_svc.cross_check_sie(target, archive, report)
    assert report.warnings == []

    # compliance data survived, with ids remapped
    imported_ver = target.query(Verification).filter(Verification.verification_number == 1).one()
    imported_pay = target.query(Verification).filter(Verification.verification_number == 2).one()
    assert imported_ver.reversed_by_verification_id == imported_pay.id
    assert imported_pay.reverses_verification_id == imported_ver.id
    assert target.query(PeriodLock).one().locked_through == date(2025, 3, 31)
    assert target.query(VerificationGapExplanation).one().fiscal_year_id == imported_ver.fiscal_year_id
    entry = (
        target.query(AuditLog)
        .filter(AuditLog.table_name == "verifications", AuditLog.user_email == test_user.email)
        .one()
    )
    assert entry.record_id == imported_ver.id and entry.summary == "insert verifications A1"
    assert target.query(AuditLog).filter(AuditLog.company_id.is_(None), AuditLog.action == "note").count() == 1

    imported = target.query(Company).one()
    assert imported.org_number == company.org_number
    assert (
        target.query(User).filter(User.email == "testuser@example.com").one().hashed_password
        == archive.users[0].hashed_password
    )
    imported_bot = target.query(User).filter(User.is_service_account.is_(True)).one()
    assert imported_bot.owner.email == "testuser@example.com" and imported_bot.api_key_hash == "sha256:deadbeef"
    assert target.query(BackupSchedule).one().max_backups == 14
    inv = target.query(Invoice).one()
    assert inv.invoice_verification.verification_number == 1
    assert inv.payments[0].bank_account.account_number == 1930
    assert {link.entity_type for link in target.query(AttachmentLink).all()} == {
        EntityType.VERIFICATION,
        EntityType.INVOICE,
    }
    assert target.query(FiscalYear).one().id == target.query(Account).first().fiscal_year_id

    # Export the imported database again: must equal the first archive
    second = tmp_path / "second.zip"
    export_svc.export_archive(target, second, scope="instance", uploads_dir=uploads2)
    assert _data_members(second) == _data_members(first)


def test_company_scope_has_no_users_or_credentials(db_session, seeded, tmp_path):
    company, uploads = seeded
    out = tmp_path / "company.zip"
    manifest = export_svc.export_archive(
        db_session, out, scope="company", company_ids=[company.id], uploads_dir=uploads
    )
    assert manifest.scope == "company"
    assert manifest.includes_credentials is False
    with zipfile.ZipFile(out) as zf:
        assert "instance/users.json" not in zf.namelist()
    archive = import_svc.verify_archive(out)
    assert archive.users == []

    # Importing into a database where the org number exists is refused
    with pytest.raises(import_svc.ArchiveError, match="already exists"):
        import_svc.load_archive(db_session, archive, uploads_target=None, import_users=False)
    db_session.rollback()

    # Importing into another instance: unknown users are dropped from company access,
    # and required creator references fall back to the importing admin.
    target = _fresh_session()
    with pytest.raises(import_svc.ArchiveError, match="no user exists"):
        import_svc.load_archive(target, archive, uploads_target=tmp_path / "u3", import_users=False)
    target.rollback()

    admin = User(email="admin@other.se", full_name="Admin", is_admin=True, hashed_password="x")
    target.add(admin)
    target.commit()
    report = import_svc.load_archive(
        target, archive, uploads_target=tmp_path / "u3", import_users=False, fallback_user=admin
    )
    target.commit()
    assert report.created["companies"] == 1
    assert report.created.get("company_users", 0) == 0
    assert any("testuser@example.com not found" in w for w in report.warnings)
    assert report.created["attachments"] == 2
    assert {a.created_by for a in target.query(Attachment).all()} == {admin.id}


def test_verify_detects_tampering(db_session, seeded, tmp_path):
    company, uploads = seeded
    good = tmp_path / "good.zip"
    export_svc.export_archive(db_session, good, uploads_dir=uploads)

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(good) as src, zipfile.ZipFile(tampered, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename.endswith("verifications.jsonl"):
                data = data.replace(b'"1250.00"', b'"1350.00"', 1)
            dst.writestr(item, data)
    with pytest.raises(import_svc.ArchiveError, match="SHA-256"):
        import_svc.verify_archive(tampered)

    truncated = tmp_path / "truncated.zip"
    with zipfile.ZipFile(good) as src, zipfile.ZipFile(truncated, "w") as dst:
        for item in src.infolist():
            if item.filename == "files/attachments/aaaa-receipt.pdf":
                continue
            dst.writestr(item, src.read(item.filename))
    with pytest.raises(import_svc.ArchiveError, match="missing"):
        import_svc.verify_archive(truncated)


def test_unbalanced_verification_is_rejected(db_session, seeded, tmp_path):
    company, uploads = seeded
    good = tmp_path / "good.zip"
    export_svc.export_archive(db_session, good, uploads_dir=uploads)

    # Rewrite one verification so it no longer balances, and fix the manifest hash
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(good) as src:
        members = {i.filename: src.read(i.filename) for i in src.infolist()}
    manifest = json.loads(members["manifest.json"])
    ver_name = next(n for n in members if n.endswith("verifications.jsonl"))
    members[ver_name] = members[ver_name].replace(b'"credit":"250.00"', b'"credit":"200.00"', 1)
    for entry in manifest["files"]:
        if entry["path"] == ver_name:
            entry["bytes"] = len(members[ver_name])
            entry["sha256"] = hashlib.sha256(members[ver_name]).hexdigest()
    members["manifest.json"] = json.dumps(manifest).encode()
    with zipfile.ZipFile(bad, "w") as dst:
        for name, data in members.items():
            dst.writestr(name, data)
    with pytest.raises(import_svc.ArchiveError, match="does not balance"):
        import_svc.verify_archive(bad)
