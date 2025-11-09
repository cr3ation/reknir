from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import date
from app.models.invoice import Invoice, InvoiceLine, SupplierInvoice, SupplierInvoiceLine, InvoiceStatus
from app.models.verification import Verification, TransactionLine
from app.models.account import Account
from typing import Optional


def create_invoice_verification(
    db: Session,
    invoice: Invoice,
    description: Optional[str] = None
) -> Verification:
    """
    Create automatic verification when invoice is created/sent

    Debit:  1510 Kundfordringar
    Credit: 3xxx Revenue accounts (from invoice lines)
    Credit: 26xx VAT accounts (based on VAT rates)
    """

    # Get next verification number
    from app.routers.verifications import get_next_verification_number
    ver_number = get_next_verification_number(db, invoice.company_id, "A")

    # Create verification
    verification = Verification(
        company_id=invoice.company_id,
        verification_number=ver_number,
        series="A",
        transaction_date=invoice.invoice_date,
        description=description or f"Faktura {invoice.invoice_series}{invoice.invoice_number} - {invoice.customer.name}",
        registration_date=date.today()
    )
    db.add(verification)
    db.flush()

    # Debit: Customer receivables (1510)
    receivables_account = db.query(Account).filter(
        Account.company_id == invoice.company_id,
        Account.account_number == 1510
    ).first()

    if not receivables_account:
        raise ValueError("Account 1510 (Kundfordringar) not found. Please import BAS accounts first.")

    debit_line = TransactionLine(
        verification_id=verification.id,
        account_id=receivables_account.id,
        debit=invoice.total_amount,
        credit=Decimal("0"),
        description=f"Faktura {invoice.invoice_series}{invoice.invoice_number}"
    )
    db.add(debit_line)
    receivables_account.current_balance += invoice.total_amount

    # Credit: Revenue accounts (from invoice lines)
    vat_by_rate = {}  # Track VAT amounts by rate

    for line in invoice.invoice_lines:
        # Revenue account - use line's account or default to 3011 based on VAT rate
        if line.account_id:
            account_id = line.account_id
        else:
            # Default revenue account based on VAT rate
            vat_rate = float(line.vat_rate)
            if vat_rate == 25.0:
                default_account_number = 3011  # Försäljning tjänster inom Sverige, 25% moms
            elif vat_rate == 12.0:
                default_account_number = 3012  # Försäljning tjänster inom Sverige, 12% moms
            elif vat_rate == 6.0:
                default_account_number = 3013  # Försäljning tjänster inom Sverige, 6% moms
            else:
                default_account_number = 3106  # Försäljning tjänster utanför EU, 0% moms

            default_account = db.query(Account).filter(
                Account.company_id == invoice.company_id,
                Account.account_number == default_account_number
            ).first()

            if not default_account:
                raise ValueError(f"Default revenue account {default_account_number} not found. Please import BAS accounts first.")

            account_id = default_account.id

        account = db.query(Account).filter(Account.id == account_id).first()
        credit_line = TransactionLine(
            verification_id=verification.id,
            account_id=account_id,
            debit=Decimal("0"),
            credit=line.net_amount,
            description=line.description
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
    vat_account_mapping = {
        25.0: 2611,  # Utgående moms 25%
        12.0: 2612,  # Utgående moms 12%
        6.0: 2613,   # Utgående moms 6%
    }

    for vat_rate, vat_amount in vat_by_rate.items():
        vat_account_number = vat_account_mapping.get(vat_rate)
        if vat_account_number:
            vat_account = db.query(Account).filter(
                Account.company_id == invoice.company_id,
                Account.account_number == vat_account_number
            ).first()

            if vat_account:
                vat_line = TransactionLine(
                    verification_id=verification.id,
                    account_id=vat_account.id,
                    debit=Decimal("0"),
                    credit=vat_amount,
                    description=f"Utgående moms {int(vat_rate)}%"
                )
                db.add(vat_line)
                vat_account.current_balance -= vat_amount

    db.commit()
    db.refresh(verification)
    return verification


def create_invoice_payment_verification(
    db: Session,
    invoice: Invoice,
    paid_date: date,
    paid_amount: Decimal,
    bank_account_id: Optional[int] = None
) -> Verification:
    """
    Create automatic verification when invoice is paid

    Debit:  1930 Bank account (or specified)
    Credit: 1510 Customer receivables
    """

    from app.routers.verifications import get_next_verification_number
    ver_number = get_next_verification_number(db, invoice.company_id, "A")

    verification = Verification(
        company_id=invoice.company_id,
        verification_number=ver_number,
        series="A",
        transaction_date=paid_date,
        description=f"Betalning faktura {invoice.invoice_series}{invoice.invoice_number} - {invoice.customer.name}",
        registration_date=date.today()
    )
    db.add(verification)
    db.flush()

    # Debit: Bank account
    if not bank_account_id:
        # Default to 1930 (Företagskonto)
        bank_account = db.query(Account).filter(
            Account.company_id == invoice.company_id,
            Account.account_number == 1930
        ).first()
    else:
        bank_account = db.query(Account).filter(Account.id == bank_account_id).first()

    if not bank_account:
        raise ValueError("Bank account not found")

    debit_line = TransactionLine(
        verification_id=verification.id,
        account_id=bank_account.id,
        debit=paid_amount,
        credit=Decimal("0"),
        description=f"Betalning faktura {invoice.invoice_series}{invoice.invoice_number}"
    )
    db.add(debit_line)
    bank_account.current_balance += paid_amount

    # Credit: Customer receivables
    receivables_account = db.query(Account).filter(
        Account.company_id == invoice.company_id,
        Account.account_number == 1510
    ).first()

    credit_line = TransactionLine(
        verification_id=verification.id,
        account_id=receivables_account.id,
        debit=Decimal("0"),
        credit=paid_amount,
        description=f"Betalning faktura {invoice.invoice_series}{invoice.invoice_number}"
    )
    db.add(credit_line)
    receivables_account.current_balance -= paid_amount

    db.commit()
    db.refresh(verification)
    return verification


def create_supplier_invoice_verification(
    db: Session,
    supplier_invoice: SupplierInvoice,
    description: Optional[str] = None
) -> Verification:
    """
    Create automatic verification when supplier invoice is registered

    Debit:  6xxx Expense accounts (from invoice lines)
    Debit:  2640 Ingående moms (input VAT)
    Credit: 2440 Leverantörsskulder (accounts payable)
    """

    from app.routers.verifications import get_next_verification_number
    ver_number = get_next_verification_number(db, supplier_invoice.company_id, "A")

    verification = Verification(
        company_id=supplier_invoice.company_id,
        verification_number=ver_number,
        series="A",
        transaction_date=supplier_invoice.invoice_date,
        description=description or f"Leverantörsfaktura {supplier_invoice.supplier_invoice_number} - {supplier_invoice.supplier.name}",
        registration_date=date.today()
    )
    db.add(verification)
    db.flush()

    # Debit: Expense accounts (from invoice lines)
    total_vat = Decimal("0")

    for line in supplier_invoice.supplier_invoice_lines:
        # Expense account - use line's account or default to 6570 (General expenses)
        if line.account_id:
            account_id = line.account_id
        else:
            # Default to general expenses account
            default_account = db.query(Account).filter(
                Account.company_id == supplier_invoice.company_id,
                Account.account_number == 6570  # Övriga externa tjänster
            ).first()

            if not default_account:
                raise ValueError("Default expense account 6570 not found. Please import BAS accounts first.")

            account_id = default_account.id

        account = db.query(Account).filter(Account.id == account_id).first()
        debit_line = TransactionLine(
            verification_id=verification.id,
            account_id=account_id,
            debit=line.net_amount,
            credit=Decimal("0"),
            description=line.description
        )
        db.add(debit_line)
        account.current_balance += line.net_amount  # Expense increases account balance

        total_vat += line.vat_amount

    # Debit: Input VAT (2640)
    if total_vat > 0:
        vat_account = db.query(Account).filter(
            Account.company_id == supplier_invoice.company_id,
            Account.account_number == 2640
        ).first()

        if vat_account:
            vat_line = TransactionLine(
                verification_id=verification.id,
                account_id=vat_account.id,
                debit=total_vat,
                credit=Decimal("0"),
                description="Ingående moms"
            )
            db.add(vat_line)
            vat_account.current_balance += total_vat

    # Credit: Accounts payable (2440)
    payables_account = db.query(Account).filter(
        Account.company_id == supplier_invoice.company_id,
        Account.account_number == 2440
    ).first()

    if not payables_account:
        raise ValueError("Account 2440 (Leverantörsskulder) not found. Please import BAS accounts first.")

    credit_line = TransactionLine(
        verification_id=verification.id,
        account_id=payables_account.id,
        debit=Decimal("0"),
        credit=supplier_invoice.total_amount,
        description=f"Faktura {supplier_invoice.supplier_invoice_number}"
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
    bank_account_id: Optional[int] = None
) -> Verification:
    """
    Create automatic verification when supplier invoice is paid

    Debit:  2440 Accounts payable
    Credit: 1930 Bank account
    """

    from app.routers.verifications import get_next_verification_number
    ver_number = get_next_verification_number(db, supplier_invoice.company_id, "A")

    verification = Verification(
        company_id=supplier_invoice.company_id,
        verification_number=ver_number,
        series="A",
        transaction_date=paid_date,
        description=f"Betalning faktura {supplier_invoice.supplier_invoice_number} - {supplier_invoice.supplier.name}",
        registration_date=date.today()
    )
    db.add(verification)
    db.flush()

    # Debit: Accounts payable
    payables_account = db.query(Account).filter(
        Account.company_id == supplier_invoice.company_id,
        Account.account_number == 2440
    ).first()

    debit_line = TransactionLine(
        verification_id=verification.id,
        account_id=payables_account.id,
        debit=paid_amount,
        credit=Decimal("0"),
        description=f"Betalning faktura {supplier_invoice.supplier_invoice_number}"
    )
    db.add(debit_line)
    payables_account.current_balance += paid_amount

    # Credit: Bank account
    if not bank_account_id:
        bank_account = db.query(Account).filter(
            Account.company_id == supplier_invoice.company_id,
            Account.account_number == 1930
        ).first()
    else:
        bank_account = db.query(Account).filter(Account.id == bank_account_id).first()

    if not bank_account:
        raise ValueError("Bank account not found")

    credit_line = TransactionLine(
        verification_id=verification.id,
        account_id=bank_account.id,
        debit=Decimal("0"),
        credit=paid_amount,
        description=f"Betalning faktura {supplier_invoice.supplier_invoice_number}"
    )
    db.add(credit_line)
    bank_account.current_balance -= paid_amount

    db.commit()
    db.refresh(verification)
    return verification
