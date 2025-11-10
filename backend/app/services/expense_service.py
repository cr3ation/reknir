from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import date
from app.models.expense import Expense
from app.models.verification import Verification, TransactionLine
from app.models.account import Account
from typing import Optional


def create_expense_verification(
    db: Session,
    expense: Expense,
    employee_payable_account_id: int,
    description: Optional[str] = None
) -> Verification:
    """
    Create automatic verification when expense is approved/booked

    Swedish: Bokför utlägg

    Debit:  Cost account (e.g., 6540 Resor)
    Debit:  VAT incoming account (e.g., 2641)
    Credit: 2890 Upplupna kostnader eller annan skuldkonto (Employee payable)
    """

    # Get next verification number
    from app.routers.verifications import get_next_verification_number
    ver_number = get_next_verification_number(db, expense.company_id, "A")

    # Create verification
    verification = Verification(
        company_id=expense.company_id,
        verification_number=ver_number,
        series="A",
        transaction_date=expense.expense_date,
        description=description or f"Utlägg - {expense.employee_name}: {expense.description}",
        registration_date=date.today()
    )
    db.add(verification)
    db.flush()

    # Debit: Expense account
    if not expense.expense_account_id:
        raise ValueError("Expense account must be set to create verification")

    expense_account = db.query(Account).filter(Account.id == expense.expense_account_id).first()
    if not expense_account:
        raise ValueError(f"Expense account {expense.expense_account_id} not found")

    net_amount = expense.amount - expense.vat_amount

    debit_expense_line = TransactionLine(
        verification_id=verification.id,
        account_id=expense_account.id,
        debit=net_amount,
        credit=Decimal("0"),
        description=expense.description
    )
    db.add(debit_expense_line)
    expense_account.current_balance += net_amount

    # Debit: VAT incoming account (if VAT exists)
    if expense.vat_amount > 0:
        if not expense.vat_account_id:
            raise ValueError("VAT account must be set when expense has VAT")

        vat_account = db.query(Account).filter(Account.id == expense.vat_account_id).first()
        if not vat_account:
            raise ValueError(f"VAT account {expense.vat_account_id} not found")

        debit_vat_line = TransactionLine(
            verification_id=verification.id,
            account_id=vat_account.id,
            debit=expense.vat_amount,
            credit=Decimal("0"),
            description=f"Moms {expense.description}"
        )
        db.add(debit_vat_line)
        vat_account.current_balance += expense.vat_amount

    # Credit: Employee payable account (liability)
    payable_account = db.query(Account).filter(Account.id == employee_payable_account_id).first()
    if not payable_account:
        raise ValueError(f"Employee payable account {employee_payable_account_id} not found")

    credit_line = TransactionLine(
        verification_id=verification.id,
        account_id=payable_account.id,
        debit=Decimal("0"),
        credit=expense.amount,
        description=f"Skuld till {expense.employee_name}"
    )
    db.add(credit_line)
    payable_account.current_balance -= expense.amount

    db.commit()
    db.refresh(verification)

    return verification
