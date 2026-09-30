"""Bokio export folder -> Reknir company archive -> import."""

import zipfile
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.account import Account
from app.models.attachment import Attachment, AttachmentLink
from app.models.company import Company
from app.models.customer import Customer
from app.models.fiscal_year import FiscalYear
from app.models.invoice import Invoice
from app.models.user import User
from app.models.verification import Verification
from app.services import archive_import_service as import_svc
from app.services import bokio_import_service as bokio

SIE_2024 = """#FLAGGA 0
#PROGRAM "Bokio" 1.0
#FORMAT PC8
#GEN 20260929
#SIETYP 4
#ORGNR 5565779039
#FNAMN "BotBox AB"
#RAR 0 20240101 20241231
#RAR -1 20230101 20231231
#KPTYP BAS2014
#KONTO 1510 "Kundfordringar"
#SRU 1510 7251
#KONTO 1930 "Företagskonto"
#SRU 1930 7281
#KONTO 2610 "Utgående moms 25%"
#KONTO 3011 "Försäljning tjänster 25%"
#KONTO 2890 "Övriga kortfristiga skulder"
#KONTO 5410 "Förbrukningsinventarier"
#IB 0 1930 50000.00
#UB 0 1930 50000.00
#UB 0 1510 125000.00
#UB 0 2610 -25000.00
#UB 0 2890 -1250.00
#RES 0 3011 -100000.00
#RES 0 5410 1250.00
#VER "V" "1" 20241221 "Faktura #5 Widenarrow Sweden AB" 20241221
{
	#TRANS 1510 {} 125000.00
	#TRANS 3011 {} -100000.00
	#TRANS 2610 {} -25000.00
}
#VER "V" "2" 20241230 "Tangentbord - Inköp förbrukningsinventarier" 20250105
{
	#TRANS 5410 {} 1250.00
	#TRANS 2890 {} -1250.00 "utlägg Joakim"
}
"""

SIE_2025 = """#FLAGGA 0
#FORMAT PC8
#SIETYP 4
#ORGNR 5565779039
#FNAMN "BotBox AB"
#RAR 0 20250101 20251231
#KONTO 1510 "Kundfordringar"
#KONTO 1930 "Företagskonto"
#IB 0 1510 125000.00
#IB 0 1930 50000.00
#UB 0 1510 0.00
#UB 0 1930 175000.00
#VER "V" "1" 20250121 "Faktura #5 betalad av Widenarrow Sweden AB (V36)" 20250208
{
	#TRANS 1510 {} -125000.00
	#TRANS 1930 {} 125000.00
}
"""

CUSTOMERS = (
    "Customer number,Name,Type,Organisation number,Vat number,Street 1,Street 2,Postal code,City,Contact,Email,Phone,"
    "Language,Payment terms,Delivery terms,Delay interest,Country,Country ISO2,Country subdiv,Id\n"
    "1,Widenarrow Sweden AB,Company,5565596953,SE556559695301,KARLAVÄGEN 58,,114 49,Stockholm,Arvid,,08221130,,30,,,,,,x\n"
)
SUMMARY_HEADER = (
    "Id,InvoiceDate,InvoiceNumber,AccountingType,SumDomestic,TaxDomestic,TotalSumDomestic,Sum,SumReceived,TotalSum,Tax,"
    "TaxRate,Currency,CurrencyRateValue,Deadline,DisableBookkeeping,InvoiceFee,Rounding,State,Type,CustomerNumber,"
    "Receiver_OrgNumber,Name,ContactName,Receiver_Email,IsForeign,Language,Receiver_TaxRegistrationNumber,Type,"
    "DelayInterest,DeliveryTerms,PaymentTerms,Receiver_Street1,Receiver_Street2,Receiver_PostalCode,Receiver_City,"
    "Receiver_Country,CountryIso2,CountrySubdivision,Sender_Street1,Sender_Street2,Sender_PostalCode,Sender_City,"
    "Sender_Country,Sender_CompanyName,Sender_Email,Sender_ForeignPaymentMethod_Key,Sender_ForeignPaymentMethod_PrimaryLabel,"
    "Sender_ForeignPaymentMethod_PrimaryValue,Sender_ForeignPaymentMethod_SecondaryLabel,Sender_ForeignPaymentMethod_SecondaryValue,"
    "Sender_PaymentMethod_Key,Sender_PaymentMethod_PrimaryLabel,Sender_PaymentMethod_PrimaryValue,Sender_PaymentMethod_SecondaryLabel,"
    "Sender_PaymentMethod_SecondaryValue,Sender_OrgNumber,Phone,ReferenceName,Sender_TaxRegistrationNumber\n"
)
SUMMARY_ROW = (
    "inv-5,2024-12-21,5,Invoice,100000,25000,125000,100000,125000,125000,25000,0,SEK,1,2025-01-20,False,0,0,Paid,Invoice,1,"
    "5565596953,Widenarrow Sweden AB,Arvid,,False,sv-SE,SE556559695301,Company,,,30,KARLAVÄGEN 58,,114 49,Stockholm,,,,"
    "C/O RISE AB,BOX 1263,164 29,Kista,,BotBox AB,info@botbox.se,,,,,,BankAccount,Bankkonto,6921-22128,,,5565779039,,,\n"
)
ROWS_HEADER = (
    "Id,InvoiceDate,InvoiceNumber,AccountingType,SumDomestic,TaxDomestic,TotalSumDomestic,Sum,SumReceived,TotalSum,Tax,"
    "TaxRate,Currency,CurrencyRateValue,Deadline,InvoiceFee,Rounding,State,Type,CustomerNumber,Receiver_OrgNumber,Name,"
    "Receiver_TaxRegistrationNumber,Type,Receiver_PostalCode,Receiver_City,Receiver_Country,CountryIso2,CountrySubdivision,"
    "RowId,ProductCode,Units,UnitType,UnitPrice,Tax,Description,ArticleId,IsTextRow,Kind\n"
)
ROWS_ROW = (
    "inv-5,2024-12-21,5,Invoice,100000,25000,125000,100000,125000,125000,25000,0,SEK,1,2025-01-20,0,0,Paid,Invoice,1,"
    "5565596953,Widenarrow Sweden AB,SE556559695301,Company,114 49,Stockholm,,,,r1,,1,Unspecified,100000,0.25,Licens BotBox IMS,,False,Services\n"
)


@pytest.fixture
def export_dir(tmp_path: Path) -> Path:
    d = tmp_path / "bokio"
    d.mkdir()
    (d / "5565779039_2024.se").write_bytes(SIE_2024.replace("\n", "\r\n").encode("cp437"))
    (d / "5565779039_2025.se").write_bytes(SIE_2025.replace("\n", "\r\n").encode("cp437"))
    with zipfile.ZipFile(d / "Kvitton_2024_20260929.zip", "w") as zf:
        zf.writestr("V2.pdf", b"%PDF receipt keyboard")
        zf.writestr("V2_1.png", b"PNG page 1")
        zf.writestr("V2_2.png", b"PNG page 2")
        zf.writestr("V9.pdf", b"%PDF orphan")
    with zipfile.ZipFile(d / "Kvitton_2025_20260929.zip", "w") as zf:
        pass
    with zipfile.ZipFile(d / "Kvitton_ej_bokforda_20260929.zip", "w") as zf:
        zf.writestr("2025-12-16_7a90ccf3.pdf", b"%PDF unbooked")
    (d / "Customers.csv").write_text(CUSTOMERS, encoding="utf-8")
    (d / "InvoiceSummaries.csv").write_text(SUMMARY_HEADER + SUMMARY_ROW, encoding="utf-8")
    (d / "InvoiceRows.csv").write_text(ROWS_HEADER + ROWS_ROW, encoding="utf-8")
    (d / "Articles.csv").write_text("ProductCode,Description,UnitPrice,UnitType,VAT,Kind,Id\n", encoding="utf-8")
    return d


def _fresh_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_bokio_export_becomes_importable_archive(export_dir, tmp_path):
    out = tmp_path / "botbox.zip"
    report = bokio.build_archive(export_dir, out, created_by_email="admin@example.com")

    assert report.org_number == "556577-9039"
    assert report.fiscal_years == ["2024", "2025"]
    assert report.counts["verifications"] == 3
    assert report.counts["receipts"] == 4 and report.counts["unbooked_receipts"] == 1
    assert report.counts["invoices"] == 1
    assert any("V9" in w for w in report.warnings)  # orphan receipt kept but flagged
    assert all("balances OK" in c for c in report.checks), report.checks

    archive = import_svc.verify_archive(out)  # integrity + references + balance
    data = archive.companies[0]
    assert data.company.name == "BotBox AB" and data.company.city == "Kista"
    assert data.company.clearing_number == "6921" and data.company.account_number == "22128"
    acc_1510_2024 = next(a for a in data.accounts if a.account_number == 1510 and a.fiscal_year_label == "2024")
    assert acc_1510_2024.sru_code == "7251" and acc_1510_2024.current_balance == Decimal("125000.00")
    ver2 = next(v for v in data.verifications if v.verification_number == 2)
    assert ver2.lines[1].credit == Decimal("1250.00") and ver2.lines[1].description == "utlägg Joakim"
    linked = [a for a in data.attachments if a.links]
    assert len(linked) == 3 and {a.links[0].entity_id for a in linked} == {ver2.id}
    assert sorted(a.links[0].sort_order for a in linked) == [0, 1, 2]
    inv = data.invoices[0]
    assert inv.payment_status == "paid" and inv.paid_amount == Decimal("125000.00")
    assert inv.invoice_verification_id is not None and inv.payment_verification_id is not None
    assert inv.lines[0].description == "Licens BotBox IMS" and inv.lines[0].vat_rate == Decimal("25.00")
    assert inv.lines[0].account_number == 3011
    assert inv.payments[0].bank_account_number == 1930 and inv.payments[0].payment_date.isoformat() == "2025-01-21"

    # And it loads through the ordinary company import
    db = _fresh_session()
    admin = User(email="admin@example.com", full_name="Admin", is_admin=True, hashed_password="x")
    db.add(admin)
    db.commit()
    result = import_svc.load_archive(
        db, archive, uploads_target=tmp_path / "uploads", import_users=False, fallback_user=admin
    )
    db.commit()
    assert result.created["companies"] == 1
    company = db.query(Company).one()
    assert company.org_number == "556577-9039"
    assert db.query(FiscalYear).count() == 2
    assert (
        db.query(FiscalYear).filter(FiscalYear.label == "2024").one().is_closed is False
    )  # default keeps last two open
    assert db.query(Verification).count() == 3
    assert db.query(Account).filter(Account.account_number == 1510).count() == 2
    assert db.query(Customer).one().name == "Widenarrow Sweden AB"
    assert db.query(Invoice).one().customer.org_number == "556559-6953"
    assert db.query(Attachment).count() == 5 and db.query(AttachmentLink).count() == 3
    assert (tmp_path / "uploads" / "attachments").exists()


def test_close_through_locks_years(export_dir, tmp_path):
    out = tmp_path / "botbox.zip"
    bokio.build_archive(export_dir, out, close_through=2024)
    archive = import_svc.verify_archive(out)
    years = {fy.label: fy.is_closed for fy in archive.companies[0].fiscal_years}
    assert years == {"2024": True, "2025": False}
    locked = {
        v.verification_number: v.locked
        for v in archive.companies[0].verifications
        if v.fiscal_year_id == archive.companies[0].fiscal_years[0].id
    }
    assert all(locked.values())
