"""Turn a Bokio "Exportera data" folder into a Reknir company archive.

Input: the folder with everything Bokio exports under Inställningar → Exportera
data (see docs/BOKIO_IMPORT.md):

    <orgnr>_<year>.se                SIE4 per fiscal year (cp437, CRLF)
    Kvitton_<year>_<date>.zip        receipts per year, named V12.pdf / V3_1.png
    Kvitton_ej_bokforda_<date>.zip   unbooked receipts, named <date>_<uuid>.pdf
    Customers.csv                    customer register
    InvoiceSummaries.csv             one row per invoice
    InvoiceRows.csv                  one row per invoice line
    Articles.csv, Employees.csv      ignored (empty / not applicable)

Output: a company-scope archive (see archive_export_service) that goes through
the ordinary ``import-company`` with all of its checks. Nothing here touches a
database.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import mimetypes
import re
import tempfile
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from app import __version__
from app.schemas import archive as fmt
from app.services.archive_export_service import ATTACHMENTS_SUBDIR, _ZipWriter
from app.services.sie4_service import _determine_account_type, _parse_sie_line

logger = logging.getLogger(__name__)

RECEIPT_NAME = re.compile(r"^([A-Za-z]+)(\d+)(?:_(\d+))?\.(pdf|png|jpe?g|gif)$", re.IGNORECASE)
INVOICE_REF = re.compile(r"Faktura\s*#?\s*(\d+)\b", re.IGNORECASE)
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif"}


class BokioImportError(Exception):
    pass


@dataclass
class BokioImportReport:
    company: str = ""
    org_number: str = ""
    fiscal_years: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)  # per-year reconciliation lines

    def bump(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n


# ---------------------------------------------------------------------------
# SIE parsing
# ---------------------------------------------------------------------------


@dataclass
class SieYear:
    path: Path
    start: date
    end: date
    company_name: str = ""
    org_number: str = ""
    accounts: dict[int, str] = field(default_factory=dict)
    sru: dict[int, str] = field(default_factory=dict)
    ib: dict[int, Decimal] = field(default_factory=dict)
    ub: dict[int, Decimal] = field(default_factory=dict)
    res: dict[int, Decimal] = field(default_factory=dict)
    verifications: list[dict] = field(default_factory=list)

    @property
    def label(self) -> str:
        return str(self.start.year) if self.start.year == self.end.year else f"{self.start.year}/{self.end.year}"


def _read_sie(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("cp437", "iso-8859-1", "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise BokioImportError(f"{path.name}: cannot decode")


def _sie_date(text: str) -> date:
    return datetime.strptime(text, "%Y%m%d").date()


def parse_sie_year(path: Path) -> SieYear:
    year: SieYear | None = None
    company_name = ""
    org_number = ""
    accounts: dict[int, str] = {}
    sru: dict[int, str] = {}
    ib: dict[int, Decimal] = {}
    ub: dict[int, Decimal] = {}
    res: dict[int, Decimal] = {}
    verifications: list[dict] = []
    current: dict | None = None

    for raw_line in _read_sie(path).splitlines():
        line = raw_line.strip()
        if line == "{" or line == "}":
            if line == "}" and current is not None:
                verifications.append(current)
                current = None
            continue
        command, args = _parse_sie_line(line)
        if not command:
            continue
        if command == "FNAMN" and args:
            company_name = args[0]
        elif command == "ORGNR" and args:
            org_number = args[0]
        elif command == "RAR" and len(args) >= 3 and args[0] == "0":
            year = SieYear(path=path, start=_sie_date(args[1]), end=_sie_date(args[2]))
        elif command == "KONTO" and len(args) >= 2:
            accounts[int(args[0])] = args[1]
        elif command == "SRU" and len(args) >= 2:
            sru[int(args[0])] = args[1]
        elif command in ("IB", "UB", "RES") and len(args) >= 3 and args[0] == "0":
            target = {"IB": ib, "UB": ub, "RES": res}[command]
            target[int(args[1])] = Decimal(args[2])
        elif command == "VER" and len(args) >= 4:
            current = {
                "series": args[0],
                "number": int(args[1]),
                "date": _sie_date(args[2]),
                "text": args[3] if len(args) > 3 else "",
                "registration_date": _sie_date(args[4]) if len(args) > 4 and args[4].isdigit() else _sie_date(args[2]),
                "lines": [],
            }
        elif command == "TRANS" and current is not None and len(args) >= 2:
            # _parse_sie_line drops the {} object list, so args = [account, amount, (date), ("desc")]
            amount = Decimal(args[1])
            description = None
            for extra in args[2:]:
                if not re.fullmatch(r"-?\d+(\.\d+)?", extra):
                    description = extra
            current["lines"].append({"account": int(args[0]), "amount": amount, "description": description})

    if current is not None:
        verifications.append(current)
    if year is None:
        raise BokioImportError(f"{path.name}: no #RAR 0 line")
    year.company_name, year.org_number = company_name, org_number
    year.accounts, year.sru, year.ib, year.ub, year.res, year.verifications = accounts, sru, ib, ub, res, verifications
    return year


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _format_org_number(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        return f"{digits[:6]}-{digits[6:]}"
    return raw


def _money(text: str | None) -> Decimal:
    if text is None or text.strip() == "":
        return Decimal("0")
    return Decimal(text.strip().replace(" ", "").replace(",", "."))


def _csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return []
        rows = []
        for values in reader:
            if not any(v.strip() for v in values):
                continue
            row: dict[str, str] = {}
            for i, name in enumerate(header):
                # Bokio repeats some column names (e.g. "Type"); keep the first, expose later ones with an index
                key = name if name not in row else f"{name}__{i}"
                row[key] = values[i] if i < len(values) else ""
            rows.append(row)
        return rows


def _last(row: dict[str, str], name: str) -> str:
    """Value of the last column with this name (Bokio repeats names such as 'Tax' and 'Type')."""
    keys = [k for k in row if k == name or k.startswith(f"{name}__")]
    return row[keys[-1]] if keys else ""


def _mime(filename: str) -> str:
    guess, _ = mimetypes.guess_type(filename)
    return guess or "application/octet-stream"


def _ts(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


class _Ids:
    def __init__(self):
        self.next = 1

    def __call__(self) -> int:
        n = self.next
        self.next += 1
        return n


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def build_archive(
    export_dir: Path,
    out_path: Path,
    *,
    close_through: int | None = None,
    created_by_email: str | None = None,
) -> BokioImportReport:
    """Read a Bokio export folder and write a company-scope Reknir archive.

    close_through: fiscal years ending in this year or earlier are marked closed
        and their verifications locked. Default: every year except the last two.
    """
    report = BokioImportReport()
    sie_files = sorted(export_dir.glob("*.se"))
    if not sie_files:
        raise BokioImportError(f"No SIE files (*.se) in {export_dir}")
    years = sorted((parse_sie_year(p) for p in sie_files), key=lambda y: y.start)
    org_number = _format_org_number(years[-1].org_number)
    company_name = years[-1].company_name or "Importerat företag"
    report.company, report.org_number = company_name, org_number
    report.fiscal_years = [y.label for y in years]
    if close_through is None:
        close_through = years[-2].end.year if len(years) >= 3 else 0

    ids = _Ids()
    now = datetime.now(UTC)
    tmp_dir = Path(tempfile.mkdtemp(prefix="reknir_bokio_"))
    files_dir = tmp_dir / "files"
    files_dir.mkdir()

    # ---- fiscal years, accounts, verifications ----
    fiscal_rows: list[fmt.FiscalYearRow] = []
    account_rows: list[fmt.AccountRow] = []
    verification_rows: list[fmt.VerificationRow] = []
    ver_index: dict[tuple[str, str, int], fmt.VerificationRow] = {}  # (year label, series, number)
    revenue_account_by_year: dict[str, dict[int, int]] = {}

    for y in years:
        fy_id = ids()
        closed = y.end.year <= close_through
        fiscal_rows.append(
            fmt.FiscalYearRow(
                id=fy_id, year=y.start.year, label=y.label, start_date=y.start, end_date=y.end, is_closed=closed
            )
        )
        acc_ids: dict[int, int] = {}
        used = (
            set(y.accounts)
            | set(y.ib)
            | set(y.ub)
            | set(y.res)
            | {line["account"] for v in y.verifications for line in v["lines"]}
        )
        for number in sorted(used):
            acc_id = ids()
            acc_ids[number] = acc_id
            opening = y.ib.get(number, Decimal("0"))
            if number in y.ub:
                closing = y.ub[number]
            elif number in y.res:
                closing = y.res[number]
            else:
                closing = opening + sum(
                    (line["amount"] for v in y.verifications for line in v["lines"] if line["account"] == number),
                    Decimal("0"),
                )
            account_rows.append(
                fmt.AccountRow(
                    id=acc_id,
                    fiscal_year_id=fy_id,
                    fiscal_year_label=y.label,
                    account_number=number,
                    name=y.accounts.get(number, f"Konto {number}"),
                    account_type=_determine_account_type(number).value,
                    opening_balance=opening,
                    current_balance=closing,
                    active=True,
                    is_bas_account=True,
                    sru_code=y.sru.get(number),
                )
            )
        revenue_account_by_year[y.label] = acc_ids

        debit_total = Decimal("0")
        for v in y.verifications:
            lines = []
            for line in v["lines"]:
                amount = line["amount"]
                lines.append(
                    fmt.TransactionLineRow(
                        id=ids(),
                        account_id=acc_ids[line["account"]],
                        account_number=line["account"],
                        debit=amount if amount > 0 else Decimal("0"),
                        credit=-amount if amount < 0 else Decimal("0"),
                        description=line["description"],
                    )
                )
                if amount > 0:
                    debit_total += amount
            row = fmt.VerificationRow(
                id=ids(),
                fiscal_year_id=fy_id,
                series=v["series"],
                verification_number=v["number"],
                transaction_date=v["date"],
                registration_date=v["registration_date"],
                description=v["text"],
                locked=closed,
                created_at=_ts(v["registration_date"]),
                updated_at=_ts(v["registration_date"]),
                lines=lines,
            )
            verification_rows.append(row)
            ver_index[(y.label, v["series"], v["number"])] = row

        # reconciliation: recomputed closing balance vs Bokio's #UB / #RES
        mismatches = []
        for number in sorted(used):
            expected = y.ub.get(number, y.res.get(number))
            if expected is None:
                continue
            computed = y.ib.get(number, Decimal("0")) + sum(
                (line["amount"] for v in y.verifications for line in v["lines"] if line["account"] == number),
                Decimal("0"),
            )
            if computed != expected:
                mismatches.append(f"{number}: file {expected} vs lines {computed}")
        status = "OK" if not mismatches else f"{len(mismatches)} account(s) differ: {mismatches[:3]}"
        report.checks.append(
            f"{y.label}: {len(y.verifications)} verifications, debit {debit_total:.2f}, balances {status}"
        )
        if mismatches:
            report.warnings.append(
                f"{y.label}: closing balances differ from verification lines for {len(mismatches)} account(s)"
            )

    report.bump("fiscal_years", len(fiscal_rows))
    report.bump("accounts", len(account_rows))
    report.bump("verifications", len(verification_rows))

    # ---- receipts ----
    attachment_rows: list[fmt.AttachmentRow] = []

    def add_file(
        zf: zipfile.ZipFile, member: str, original_name: str, links: list[fmt.AttachmentLinkRow], when: datetime
    ) -> None:
        ext = Path(original_name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            report.warnings.append(f"skipped {original_name}: unsupported file type")
            return
        storage_name = f"{uuid.uuid4()}{ext}"
        data = zf.read(member)
        (files_dir / storage_name).write_bytes(data)
        attachment_rows.append(
            fmt.AttachmentRow(
                id=ids(),
                original_filename=original_name,
                storage_filename=storage_name,
                mime_type=_mime(original_name),
                size_bytes=len(data),
                checksum_sha256=hashlib.sha256(data).hexdigest(),
                status="ready" if links else "uploaded",
                created_at=when,
                created_by_email=created_by_email,
                links=links,
            )
        )

    for y in years:
        zips = sorted(export_dir.glob(f"Kvitton_{y.start.year}_*.zip"))
        if not zips:
            continue
        with zipfile.ZipFile(zips[-1]) as zf:
            for member in zf.namelist():
                if member.endswith("/"):
                    continue
                name = Path(member).name
                m = RECEIPT_NAME.match(name)
                links: list[fmt.AttachmentLinkRow] = []
                if m:
                    series, number, page = m.group(1).upper(), int(m.group(2)), int(m.group(3) or 0)
                    ver = ver_index.get((y.label, series, number))
                    if ver is None:
                        report.warnings.append(
                            f"{y.label}: receipt {name} has no verification {series}{number}, kept unlinked"
                        )
                    else:
                        links = [
                            fmt.AttachmentLinkRow(
                                entity_type="verification",
                                entity_id=ver.id,
                                role="original",
                                sort_order=page,
                                created_at=now,
                            )
                        ]
                else:
                    report.warnings.append(f"{y.label}: receipt {name} does not follow V<nr> naming, kept unlinked")
                add_file(zf, member, name, links, now)
                report.bump("receipts")

    for unbooked in sorted(export_dir.glob("Kvitton_ej_bokforda_*.zip"))[-1:]:
        with zipfile.ZipFile(unbooked) as zf:
            for member in zf.namelist():
                if member.endswith("/"):
                    continue
                add_file(zf, member, Path(member).name, [], now)
                report.bump("unbooked_receipts")

    # ---- customers ----
    customer_rows: list[fmt.CustomerRow] = []
    customer_by_number: dict[str, int] = {}
    for row in _csv_rows(export_dir / "Customers.csv"):
        cid = ids()
        customer_by_number[row.get("Customer number", "").strip()] = cid
        street = ", ".join(s for s in (row.get("Street 1", ""), row.get("Street 2", "")) if s.strip())
        customer_rows.append(
            fmt.CustomerRow(
                id=cid,
                name=row.get("Name", "").strip() or "Okänd kund",
                org_number=_format_org_number(row.get("Organisation number", "")) or None,
                contact_person=row.get("Contact") or None,
                email=row.get("Email") or None,
                phone=row.get("Phone") or None,
                address=street or None,
                postal_code=(row.get("Postal code") or None),
                city=row.get("City") or None,
                country=row.get("Country") or "Sverige",
                payment_terms_days=int(row.get("Payment terms") or 30),
                active=True,
            )
        )
    report.bump("customers", len(customer_rows))

    # ---- invoices ----
    invoice_rows: list[fmt.InvoiceRow] = []
    lines_by_invoice: dict[str, list[dict[str, str]]] = {}
    for row in _csv_rows(export_dir / "InvoiceRows.csv"):
        lines_by_invoice.setdefault(row.get("Id", ""), []).append(row)

    def find_verification(number: int, invoice_date: date, payment: bool) -> fmt.VerificationRow | None:
        candidates = []
        for ver in ver_index.values():
            m = INVOICE_REF.search(ver.description)
            if not m or int(m.group(1)) != number:
                continue
            is_payment = "betal" in ver.description.lower()
            if is_payment != payment:
                continue
            candidates.append(ver)
        if not candidates:
            return None
        return min(candidates, key=lambda v: abs((v.transaction_date - invoice_date).days))

    for row in _csv_rows(export_dir / "InvoiceSummaries.csv"):
        number = int(row.get("InvoiceNumber") or 0)
        invoice_date = date.fromisoformat(row["InvoiceDate"][:10])
        due = date.fromisoformat(row["Deadline"][:10]) if row.get("Deadline") else invoice_date
        customer_id = customer_by_number.get(row.get("CustomerNumber", "").strip())
        if customer_id is None:
            cid = ids()
            customer_by_number[row.get("CustomerNumber", "").strip()] = cid
            customer_rows.append(
                fmt.CustomerRow(
                    id=cid,
                    name=row.get("Name") or "Okänd kund",
                    org_number=_format_org_number(row.get("Receiver_OrgNumber", "")) or None,
                    country="Sverige",
                    payment_terms_days=30,
                    active=True,
                )
            )
            customer_id = cid
            report.bump("customers")
        net, vat, total = _money(row.get("Sum")), _money(row.get("Tax")), _money(row.get("TotalSum"))
        received = _money(row.get("SumReceived"))
        state = (row.get("State") or "").lower()
        if state == "paid" or (received >= total and total > 0):
            payment_status = "paid"
        elif received > 0:
            payment_status = "partially_paid"
        else:
            payment_status = "unpaid"
        status = "cancelled" if state in ("cancelled", "credited", "void") else "issued"

        issue_ver = find_verification(number, invoice_date, payment=False)
        pay_ver = find_verification(number, invoice_date, payment=True)
        if issue_ver is None:
            report.warnings.append(f"invoice #{number}: no verification found with 'Faktura #{number}'")
        line_rows = []
        for lr in lines_by_invoice.get(row.get("Id", ""), []):
            if (lr.get("IsTextRow") or "").lower() == "true":
                continue
            qty = _money(lr.get("Units") or "1")
            unit_price = _money(lr.get("UnitPrice"))
            rate = _money(_last(lr, "Tax") or "0")
            vat_rate = rate * 100 if rate <= 1 else rate
            line_net = (qty * unit_price).quantize(Decimal("0.01"))
            line_vat = (line_net * vat_rate / 100).quantize(Decimal("0.01"))
            revenue = None
            if issue_ver is not None:
                for tl in issue_ver.lines:
                    if 3000 <= tl.account_number <= 3999 and tl.credit > 0:
                        revenue = tl.account_id
                        break
            line_rows.append(
                fmt.InvoiceLineRow(
                    id=ids(),
                    description=lr.get("Description") or "Rad",
                    quantity=qty,
                    unit=(lr.get("UnitType") or "st")[:20].replace("Unspecified", "st"),
                    unit_price=unit_price,
                    vat_rate=vat_rate,
                    account_id=revenue,
                    account_number=next(
                        (
                            tl.account_number
                            for tl in (issue_ver.lines if issue_ver else [])
                            if tl.account_id == revenue
                        ),
                        None,
                    ),
                    net_amount=line_net,
                    vat_amount=line_vat,
                    total_amount=line_net + line_vat,
                )
            )
        if not line_rows:
            line_rows.append(
                fmt.InvoiceLineRow(
                    id=ids(),
                    description=f"Faktura {number}",
                    quantity=Decimal("1"),
                    unit="st",
                    unit_price=net,
                    vat_rate=(vat / net * 100).quantize(Decimal("0.01")) if net else Decimal("0"),
                    net_amount=net,
                    vat_amount=vat,
                    total_amount=total,
                )
            )
        payments = []
        if received > 0:
            bank = None
            if pay_ver is not None:
                bank = next((tl for tl in pay_ver.lines if 1900 <= tl.account_number <= 1999 and tl.debit > 0), None)
            payments.append(
                fmt.PaymentRow(
                    id=ids(),
                    payment_date=pay_ver.transaction_date if pay_ver else due,
                    amount=received,
                    verification_id=pay_ver.id if pay_ver else None,
                    bank_account_id=bank.account_id if bank else None,
                    bank_account_number=bank.account_number if bank else None,
                    reference=f"Bokio faktura {number}",
                    created_at=now,
                )
            )
        invoice_rows.append(
            fmt.InvoiceRow(
                id=ids(),
                customer_id=customer_id,
                invoice_number=number,
                invoice_series="F",
                invoice_date=invoice_date,
                due_date=due,
                paid_date=(pay_ver.transaction_date if pay_ver else (due if payment_status == "paid" else None)),
                reference=row.get("ReferenceName") or None,
                total_amount=total,
                vat_amount=vat,
                net_amount=net,
                status=status,
                payment_status=payment_status,
                paid_amount=received,
                notes=f"Importerad från Bokio {now.date().isoformat()} (Bokio id {row.get('Id', '')})",
                invoice_verification_id=issue_ver.id if issue_ver else None,
                payment_verification_id=pay_ver.id if pay_ver else None,
                created_at=_ts(invoice_date),
                updated_at=_ts(invoice_date),
                sent_at=_ts(invoice_date),
                lines=line_rows,
                payments=payments,
            )
        )
    report.bump("invoices", len(invoice_rows))

    # ---- company ----
    sender = next(iter(_csv_rows(export_dir / "InvoiceSummaries.csv")), {})
    payment_key = (sender.get("Sender_PaymentMethod_Key") or "").lower()
    payment_value = (sender.get("Sender_PaymentMethod_PrimaryValue") or "").strip()
    company = fmt.CompanyRow(
        id=ids(),
        name=company_name,
        org_number=org_number,
        address=", ".join(s for s in (sender.get("Sender_Street1", ""), sender.get("Sender_Street2", "")) if s.strip())
        or None,
        postal_code=(sender.get("Sender_PostalCode") or None),
        city=sender.get("Sender_City") or None,
        phone=sender.get("Phone") or None,
        email=sender.get("Sender_Email") or None,
        fiscal_year_start=years[-1].start,
        fiscal_year_end=years[-1].end,
        accounting_basis="accrual",
        vat_reporting_period="quarterly",
        is_vat_registered=True,
        payment_type=(
            "bankgiro"
            if "bankgiro" in payment_key
            else "plusgiro"
            if "plusgiro" in payment_key
            else "bank_account"
            if payment_value
            else None
        ),
        bankgiro_number=payment_value if "bankgiro" in payment_key else None,
        plusgiro_number=payment_value if "plusgiro" in payment_key else None,
        clearing_number=(
            payment_value.split("-")[0] if payment_key == "bankaccount" and "-" in payment_value else None
        ),
        account_number=(
            payment_value.split("-", 1)[1] if payment_key == "bankaccount" and "-" in payment_value else None
        ),
    )

    # ---- write archive ----
    base = f"companies/{re.sub(r'[^0-9A-Za-z-]', '', org_number)}"
    writer = _ZipWriter(out_path)
    try:
        import json

        for name, model in fmt.SCHEMA_MODELS.items():
            writer.write_text(f"schema/{name}.schema.json", json.dumps(model.model_json_schema(), indent=2) + "\n")
        writer.write_text(f"{base}/company.json", company.model_dump_json(indent=2) + "\n")
        writer.write_json(f"{base}/company_users.json", [])
        writer.write_json(f"{base}/fiscal_years.json", fiscal_rows)
        writer.write_jsonl(f"{base}/accounts.jsonl", account_rows)
        writer.write_jsonl(f"{base}/verifications.jsonl", verification_rows)
        writer.write_json(f"{base}/customers.json", customer_rows)
        writer.write_json(f"{base}/suppliers.json", [])
        writer.write_jsonl(f"{base}/invoices.jsonl", invoice_rows)
        writer.write_jsonl(f"{base}/supplier_invoices.jsonl", [])
        writer.write_jsonl(f"{base}/expenses.jsonl", [])
        writer.write_json(f"{base}/posting_templates.json", [])
        writer.write_json(f"{base}/default_accounts.json", [])
        writer.write_jsonl(f"{base}/attachments.jsonl", attachment_rows)
        for att in attachment_rows:
            writer.write_file(f"files/{ATTACHMENTS_SUBDIR}/{att.storage_filename}", files_dir / att.storage_filename)
        for sie in sie_files:
            writer.write_file(f"{base}/bokio/{sie.name}", sie)
        manifest = fmt.Manifest(
            scope="company",
            created_at=now,
            app_version=__version__,
            schema_version="bokio-export",
            includes_credentials=False,
            includes_ai=False,
            companies=[fmt.CompanyEntry(org_number=org_number, name=company_name, path=base)],
            counts={**report.counts, "files": len(attachment_rows)},
            warnings=report.warnings,
            files=writer.entries,
        )
        writer.zip.writestr("manifest.json", manifest.model_dump_json(indent=2) + "\n")
    finally:
        writer.close()
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)

    report.bump("attachments", len(attachment_rows))
    return report
