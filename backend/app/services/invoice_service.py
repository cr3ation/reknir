from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.default_account import DefaultAccountType
from app.models.fiscal_year import FiscalYear
from app.models.invoice import Invoice, SupplierInvoice
from app.models.verification import TransactionLine, Verification
from app.services import default_account_service


def get_fiscal_year_for_date(db: Session, company_id: int, transaction_date: date) -> FiscalYear:
    """
    Get the fiscal year for a given transaction date.
    Raises ValueError if no fiscal year is found.
    """
    fiscal_year = (
        db.query(FiscalYear)
        .filter(
            FiscalYear.company_id == company_id,
            FiscalYear.start_date <= transaction_date,
            FiscalYear.end_date >= transaction_date,
        )
        .first()
    )

    if not fiscal_year:
        raise ValueError(
            f"No fiscal year found for date {transaction_date}. Please create a fiscal year that includes this date."
        )

    return fiscal_year


def create_invoice_verification(db: Session, invoice: Invoice, description: str | None = None) -> Verification:
    """
    Create automatic verification when invoice is created/sent

    Debit:  1510 Kundfordringar
    Credit: 3xxx Revenue accounts (from invoice lines)
    Credit: 26xx VAT accounts (based on VAT rates)
    """

    # Get fiscal year for this invoice date
    fiscal_year = get_fiscal_year_for_date(db, invoice.company_id, invoice.invoice_date)

    # Get next verification number
    from app.routers.verifications import get_next_verification_number

    ver_number = get_next_verification_number(db, invoice.company_id, "A")

    # Create verification
    verification = Verification(
        company_id=invoice.company_id,
        fiscal_year_id=fiscal_year.id,
        verification_number=ver_number,
        series="A",
        transaction_date=invoice.invoice_date,
        description=description
        or f"Faktura {invoice.invoice_series}{invoice.invoice_number} - {invoice.customer.name}",
        registration_date=date.today(),
    )
    db.add(verification)
    db.flush()

    # Debit: Customer receivables
    receivables_account = default_account_service.get_default_account(
        db, invoice.company_id, fiscal_year.id, DefaultAccountType.ACCOUNTS_RECEIVABLE
    )

    if not receivables_account:
        raise ValueError(
            "Default accounts receivable account not configured. Please configure default accounts or import BAS accounts."
        )

    debit_line = TransactionLine(
        verification_id=verification.id,
        account_id=receivables_account.id,
        debit=invoice.total_amount,
        credit=Decimal("0"),
        description=f"Faktura {invoice.invoice_series}{invoice.invoice_number}",
    )
    db.add(debit_line)
    receivables_account.current_balance += invoice.total_amount

    # Credit: Revenue accounts (from invoice lines)
    vat_by_rate = {}  # Track VAT amounts by rate

    for line in invoice.invoice_lines:
        # Revenue account - use line's account or default based on VAT rate
        if line.account_id:
            account = db.query(Account).filter(Account.id == line.account_id).first()
        else:
            # Get default revenue account based on VAT rate
            account = default_account_service.get_revenue_account_for_vat_rate(
                db, invoice.company_id, fiscal_year.id, line.vat_rate
            )

            if not account:
                raise ValueError(
                    f"Default revenue account for VAT rate {line.vat_rate}% not configured. Please configure default accounts or import BAS accounts."
                )

        credit_line = TransactionLine(
            verification_id=verification.id,
            account_id=account.id,
            debit=Decimal("0"),
            credit=line.net_amount,
            description=line.description,
        )
        db.add(credit_line)
        account.current_balance -= line.net_amount  # Revenue decreases account balance

        # Accumulate VAT by rate
        vat_rate = float(line.vat_rate)
        if vat_rate > 0:
            if vat_rate not in vat_by_rate:
                vat_by_rate[vat_rate] = Decimal("0")
            vat_by_rate[vat_rate] += line.vat_amount

    # Credit: VAT accounts
    for vat_rate, vat_amount in vat_by_rate.items():
        vat_account = default_account_service.get_vat_outgoing_account_for_rate(
            db, invoice.company_id, fiscal_year.id, Decimal(str(vat_rate))
        )

        if vat_account:
            vat_line = TransactionLine(
                verification_id=verification.id,
                account_id=vat_account.id,
                debit=Decimal("0"),
                credit=vat_amount,
                description=f"Utgående moms {int(vat_rate)}%",
            )
            db.add(vat_line)
            vat_account.current_balance -= vat_amount

    db.commit()
    db.refresh(verification)
    return verification


def create_invoice_payment_verification(
    db: Session, invoice: Invoice, paid_date: date, paid_amount: Decimal, bank_account_id: int | None = None
) -> Verification:
    """
    Create automatic verification when invoice is paid

    Debit:  1930 Bank account (or specified)
    Credit: 1510 Customer receivables
    """

    # Get fiscal year for payment date
    fiscal_year = get_fiscal_year_for_date(db, invoice.company_id, paid_date)

    from app.routers.verifications import get_next_verification_number

    ver_number = get_next_verification_number(db, invoice.company_id, "A")

    verification = Verification(
        company_id=invoice.company_id,
        fiscal_year_id=fiscal_year.id,
        verification_number=ver_number,
        series="A",
        transaction_date=paid_date,
        description=f"Betalning faktura {invoice.invoice_series}{invoice.invoice_number} - {invoice.customer.name}",
        registration_date=date.today(),
    )
    db.add(verification)
    db.flush()

    # Debit: Bank account
    if not bank_account_id:
        # Default to 1930 (Företagskonto)
        bank_account = (
            db.query(Account)
            .filter(
                Account.company_id == invoice.company_id,
                Account.fiscal_year_id == fiscal_year.id,
                Account.account_number == 1930,
            )
            .first()
        )
    else:
        bank_account = db.query(Account).filter(Account.id == bank_account_id).first()

    if not bank_account:
        raise ValueError("Bank account not found")

    debit_line = TransactionLine(
        verification_id=verification.id,
        account_id=bank_account.id,
        debit=paid_amount,
        credit=Decimal("0"),
        description=f"Betalning faktura {invoice.invoice_series}{invoice.invoice_number}",
    )
    db.add(debit_line)
    bank_account.current_balance += paid_amount

    # Credit: Customer receivables
    receivables_account = default_account_service.get_default_account(
        db, invoice.company_id, fiscal_year.id, DefaultAccountType.ACCOUNTS_RECEIVABLE
    )

    if not receivables_account:
        raise ValueError("Default accounts receivable account not configured.")

    credit_line = TransactionLine(
        verification_id=verification.id,
        account_id=receivables_account.id,
        debit=Decimal("0"),
        credit=paid_amount,
        description=f"Betalning faktura {invoice.invoice_series}{invoice.invoice_number}",
    )
    db.add(credit_line)
    receivables_account.current_balance -= paid_amount

    db.commit()
    db.refresh(verification)
    return verification


def create_supplier_invoice_verification(
    db: Session, supplier_invoice: SupplierInvoice, description: str | None = None
) -> Verification:
    """
    Create automatic verification when supplier invoice is registered

    Debit:  6xxx Expense accounts (from invoice lines)
    Debit:  2640 Ingående moms (input VAT)
    Credit: 2440 Leverantörsskulder (accounts payable)
    """

    # Get fiscal year for this invoice date
    fiscal_year = get_fiscal_year_for_date(db, supplier_invoice.company_id, supplier_invoice.invoice_date)

    from app.routers.verifications import get_next_verification_number

    ver_number = get_next_verification_number(db, supplier_invoice.company_id, "A")

    verification = Verification(
        company_id=supplier_invoice.company_id,
        fiscal_year_id=fiscal_year.id,
        verification_number=ver_number,
        series="A",
        transaction_date=supplier_invoice.invoice_date,
        description=description
        or f"Leverantörsfaktura {supplier_invoice.supplier_invoice_number} - {supplier_invoice.supplier.name}",
        registration_date=date.today(),
    )
    db.add(verification)
    db.flush()

    # Debit: Expense accounts (from invoice lines)
    total_vat = Decimal("0")

    for line in supplier_invoice.supplier_invoice_lines:
        # Expense account - use line's account or default
        if line.account_id:
            account = db.query(Account).filter(Account.id == line.account_id).first()
        else:
            # Get default expense account
            account = default_account_service.get_default_account(
                db, supplier_invoice.company_id, fiscal_year.id, DefaultAccountType.EXPENSE_DEFAULT
            )

            if not account:
                raise ValueError(
                    "Default expense account not configured. Please configure default accounts or import BAS accounts."
                )

        debit_line = TransactionLine(
            verification_id=verification.id,
            account_id=account.id,
            debit=line.net_amount,
            credit=Decimal("0"),
            description=line.description,
        )
        db.add(debit_line)
        account.current_balance += line.net_amount  # Expense increases account balance

        total_vat += line.vat_amount

    # Debit: Input VAT
    if total_vat > 0:
        # Use 25% incoming VAT account as default for now
        # TODO: Track VAT by rate in supplier invoices too
        vat_account = default_account_service.get_default_account(
            db, supplier_invoice.company_id, fiscal_year.id, DefaultAccountType.VAT_INCOMING_25
        )

        if vat_account:
            vat_line = TransactionLine(
                verification_id=verification.id,
                account_id=vat_account.id,
                debit=total_vat,
                credit=Decimal("0"),
                description="Ingående moms",
            )
            db.add(vat_line)
            vat_account.current_balance += total_vat

    # Credit: Accounts payable
    payables_account = default_account_service.get_default_account(
        db, supplier_invoice.company_id, fiscal_year.id, DefaultAccountType.ACCOUNTS_PAYABLE
    )

    if not payables_account:
        raise ValueError(
            "Default accounts payable account not configured. Please configure default accounts or import BAS accounts."
        )

    credit_line = TransactionLine(
        verification_id=verification.id,
        account_id=payables_account.id,
        debit=Decimal("0"),
        credit=supplier_invoice.total_amount,
        description=f"Faktura {supplier_invoice.supplier_invoice_number}",
    )
    db.add(credit_line)
    payables_account.current_balance -= supplier_invoice.total_amount

    db.commit()
    db.refresh(verification)
    return verification


def create_supplier_invoice_payment_verification(
    db: Session,
    supplier_invoice: SupplierInvoice,
    paid_date: date,
    paid_amount: Decimal,
    bank_account_id: int | None = None,
) -> Verification:
    """
    Create automatic verification when supplier invoice is paid

    Debit:  2440 Accounts payable
    Credit: 1930 Bank account
    """

    # Get fiscal year for payment date
    fiscal_year = get_fiscal_year_for_date(db, supplier_invoice.company_id, paid_date)

    from app.routers.verifications import get_next_verification_number

    ver_number = get_next_verification_number(db, supplier_invoice.company_id, "A")

    verification = Verification(
        company_id=supplier_invoice.company_id,
        fiscal_year_id=fiscal_year.id,
        verification_number=ver_number,
        series="A",
        transaction_date=paid_date,
        description=f"Betalning faktura {supplier_invoice.supplier_invoice_number} - {supplier_invoice.supplier.name}",
        registration_date=date.today(),
    )
    db.add(verification)
    db.flush()

    # Debit: Accounts payable
    payables_account = default_account_service.get_default_account(
        db, supplier_invoice.company_id, fiscal_year.id, DefaultAccountType.ACCOUNTS_PAYABLE
    )

    if not payables_account:
        raise ValueError("Default accounts payable account not configured.")

    debit_line = TransactionLine(
        verification_id=verification.id,
        account_id=payables_account.id,
        debit=paid_amount,
        credit=Decimal("0"),
        description=f"Betalning faktura {supplier_invoice.supplier_invoice_number}",
    )
    db.add(debit_line)
    payables_account.current_balance += paid_amount

    # Credit: Bank account
    if not bank_account_id:
        bank_account = (
            db.query(Account)
            .filter(
                Account.company_id == supplier_invoice.company_id,
                Account.fiscal_year_id == fiscal_year.id,
                Account.account_number == 1930,
            )
            .first()
        )
    else:
        bank_account = db.query(Account).filter(Account.id == bank_account_id).first()

    if not bank_account:
        raise ValueError("Bank account not found")

    credit_line = TransactionLine(
        verification_id=verification.id,
        account_id=bank_account.id,
        debit=Decimal("0"),
        credit=paid_amount,
        description=f"Betalning faktura {supplier_invoice.supplier_invoice_number}",
    )
    db.add(credit_line)
    bank_account.current_balance -= paid_amount

    db.commit()
    db.refresh(verification)
    return verification
