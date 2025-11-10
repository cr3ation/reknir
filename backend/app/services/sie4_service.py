"""
SIE4 Import/Export Service

SIE (Standard Import Export) is the Swedish standard for importing/exporting accounting data.
This service handles SIE4 format, which includes:
- Chart of accounts (#KONTO)
- Verifications and transactions (#VER, #TRANS)
- Balances (#IB, #UB)
- Company info (#FNAMN, #ORGNR, #RAR)
"""

from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import date, datetime
from typing import List, Dict, TextIO
import re

from app.models.company import Company
from app.models.account import Account, AccountType
from app.models.verification import Verification, TransactionLine
from app.services import default_account_service


def _determine_account_type(account_number: int) -> AccountType:
    """Determine account type based on account number (BAS kontoplan structure)"""
    if 1000 <= account_number <= 1999:
        return AccountType.ASSET
    elif 2000 <= account_number <= 2999:
        return AccountType.EQUITY_LIABILITY
    elif 3000 <= account_number <= 3999:
        return AccountType.REVENUE
    elif 4000 <= account_number <= 4999:
        return AccountType.COST_GOODS
    elif 5000 <= account_number <= 5999:
        return AccountType.COST_LOCAL
    elif 6000 <= account_number <= 6999:
        return AccountType.COST_OTHER
    elif 7000 <= account_number <= 7999:
        return AccountType.COST_PERSONNEL
    elif 8000 <= account_number <= 8999:
        return AccountType.COST_MISC
    else:
        # Default to COST_OTHER for unknown ranges
        return AccountType.COST_OTHER


def _parse_sie_line(line: str) -> tuple[str, List[str]]:
    """
    Parse a SIE4 line into command and arguments.

    Example:
        '#KONTO 1510 "Kundfordringar"' -> ('KONTO', ['1510', 'Kundfordringar'])
        '#VER "A" 1 20241109 "Description"' -> ('VER', ['A', '1', '20241109', 'Description'])
    """
    line = line.strip()
    if not line or line.startswith('#'):
        # Skip comments and empty lines (but not commands starting with #)
        if not line.startswith('#') or line == '#':
            return '', []

    # Extract command
    match = re.match(r'#(\w+)\s+(.*)', line)
    if not match:
        return '', []

    command = match.group(1)
    rest = match.group(2)

    # Parse arguments - handle quoted strings and numbers
    args = []
    current_arg = ''
    in_quotes = False

    for char in rest:
        if char == '"':
            in_quotes = not in_quotes
        elif char in (' ', '\t') and not in_quotes:
            if current_arg:
                args.append(current_arg)
                current_arg = ''
        elif char == '{' or char == '}':
            # Skip transaction delimiters
            continue
        else:
            current_arg += char

    if current_arg:
        args.append(current_arg)

    return command, args


def import_sie4(db: Session, company_id: int, file_content: str) -> Dict[str, any]:
    """
    Import SIE4 file content into the database.

    Returns a dict with import statistics:
    - accounts_created: number of accounts created
    - accounts_updated: number of accounts updated
    - verifications_created: number of verifications created
    - default_accounts_configured: number of default accounts configured
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise ValueError(f"Company {company_id} not found")

    stats = {
        'accounts_created': 0,
        'accounts_updated': 0,
        'verifications_created': 0,
        'default_accounts_configured': 0,
    }

    lines = file_content.split('\n')
    accounts_cache = {}  # Cache account number -> Account object
    current_verification = None
    verifications_to_create = []  # Store verifications to create after parsing

    for line in lines:
        command, args = _parse_sie_line(line)

        if not command:
            continue

        if command == 'KONTO':
            # #KONTO account_number "name"
            if len(args) >= 2:
                account_number = int(args[0])
                account_name = args[1]

                # Check if account exists
                existing = db.query(Account).filter(
                    Account.company_id == company_id,
                    Account.account_number == account_number
                ).first()

                if existing:
                    # Update name if different
                    if existing.name != account_name:
                        existing.name = account_name
                        stats['accounts_updated'] += 1
                    accounts_cache[account_number] = existing
                else:
                    # Create new account
                    account_type = _determine_account_type(account_number)
                    new_account = Account(
                        company_id=company_id,
                        account_number=account_number,
                        name=account_name,
                        account_type=account_type,
                        is_bas_account=False  # Imported accounts are not necessarily BAS
                    )
                    db.add(new_account)
                    db.flush()  # Get the ID
                    accounts_cache[account_number] = new_account
                    stats['accounts_created'] += 1

        elif command == 'IB':
            # #IB year account_number opening_balance
            if len(args) >= 3:
                account_number = int(args[1])
                balance = Decimal(args[2])

                if account_number in accounts_cache:
                    account = accounts_cache[account_number]
                    account.opening_balance = balance
                    account.current_balance = balance

        elif command == 'VER':
            # Save previous verification if exists
            if current_verification and current_verification['lines']:
                verifications_to_create.append(current_verification)

            # #VER series verification_number transaction_date "description"
            # Transactions follow in subsequent #TRANS lines until closing }
            if len(args) >= 3:
                current_verification = {
                    'series': args[0],
                    'number': int(args[1]),
                    'date': args[2],
                    'description': args[3] if len(args) > 3 else '',
                    'lines': []
                }

        elif command == 'TRANS':
            # #TRANS account_number {object_list} amount [transaction_date] ["description"]
            if current_verification and len(args) >= 2:
                account_number = int(args[0])

                # Parse amount - can be with or without object list {}
                amount_str = args[1]
                if amount_str == '{}' and len(args) >= 3:
                    amount_str = args[2]

                amount = Decimal(amount_str)
                description = ''
                if len(args) > 2:
                    # Last argument might be description
                    last_arg = args[-1]
                    if not last_arg.replace('.', '').replace('-', '').isdigit():
                        description = last_arg

                current_verification['lines'].append({
                    'account_number': account_number,
                    'amount': amount,
                    'description': description
                })

    # Don't forget the last verification
    if current_verification and current_verification['lines']:
        verifications_to_create.append(current_verification)

    # Commit account changes
    db.commit()

    # Reload accounts cache from database to get IDs
    all_accounts = db.query(Account).filter(Account.company_id == company_id).all()
    accounts_by_number = {acc.account_number: acc for acc in all_accounts}

    # Create verifications
    for ver_data in verifications_to_create:
        try:
            # Parse date
            date_str = ver_data['date']
            if len(date_str) == 8:  # YYYYMMDD format
                transaction_date = datetime.strptime(date_str, '%Y%m%d').date()
            else:
                # Skip if date format is invalid
                continue

            # Check if verification already exists (same series, number, and date)
            existing_ver = db.query(Verification).filter(
                Verification.company_id == company_id,
                Verification.series == ver_data['series'],
                Verification.verification_number == ver_data['number'],
                Verification.transaction_date == transaction_date
            ).first()

            if existing_ver:
                # Skip duplicate verifications
                continue

            # Create verification
            verification = Verification(
                company_id=company_id,
                series=ver_data['series'],
                verification_number=ver_data['number'],
                transaction_date=transaction_date,
                description=ver_data['description']
            )
            db.add(verification)
            db.flush()  # Get the ID

            # Create transaction lines
            for line_data in ver_data['lines']:
                account_number = line_data['account_number']
                if account_number not in accounts_by_number:
                    # Skip if account doesn't exist
                    continue

                account = accounts_by_number[account_number]
                amount = line_data['amount']

                # In SIE4: positive amount = debit, negative amount = credit
                debit = amount if amount > 0 else Decimal(0)
                credit = -amount if amount < 0 else Decimal(0)

                trans_line = TransactionLine(
                    verification_id=verification.id,
                    account_id=account.id,
                    debit=debit,
                    credit=credit,
                    description=line_data['description']
                )
                db.add(trans_line)

            stats['verifications_created'] += 1

        except Exception as e:
            # Log error but continue with other verifications
            print(f"Error creating verification: {e}")
            continue

    # Commit verifications
    db.commit()

    # Initialize default account mappings based on imported accounts
    default_account_service.initialize_default_accounts_from_existing(db, company_id)

    # Count how many defaults were configured
    from app.models.default_account import DefaultAccount
    defaults_count = db.query(DefaultAccount).filter(
        DefaultAccount.company_id == company_id
    ).count()
    stats['default_accounts_configured'] = defaults_count

    return stats


def export_sie4(db: Session, company_id: int, include_verifications: bool = True) -> str:
    """
    Export company data to SIE4 format.

    Args:
        db: Database session
        company_id: Company to export
        include_verifications: Whether to include verifications (default True)

    Returns:
        SIE4 formatted string
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise ValueError(f"Company {company_id} not found")

    lines = []

    # Header
    lines.append('#FLAGGA 0')
    lines.append('#PROGRAM "Reknir" "1.0"')
    lines.append('#FORMAT PC8')
    lines.append(f'#GEN {date.today().strftime("%Y%m%d")}')
    lines.append('#SIETYP 4')

    # Company info
    lines.append(f'#FNAMN "{company.name}"')
    lines.append(f'#ORGNR "{company.org_number}"')

    # Fiscal year
    lines.append(f'#RAR 0 {company.fiscal_year_start.strftime("%Y%m%d")} {company.fiscal_year_end.strftime("%Y%m%d")}')

    # Chart of accounts
    accounts = db.query(Account).filter(
        Account.company_id == company_id,
        Account.active == True
    ).order_by(Account.account_number).all()

    for account in accounts:
        lines.append(f'#KONTO {account.account_number} "{account.name}"')

        # Opening balance (if not zero)
        if account.opening_balance != 0:
            lines.append(f'#IB 0 {account.account_number} {account.opening_balance}')

        # Current balance (if different from opening)
        if account.current_balance != account.opening_balance:
            lines.append(f'#UB 0 {account.account_number} {account.current_balance}')

    # Verifications
    if include_verifications:
        verifications = db.query(Verification).filter(
            Verification.company_id == company_id
        ).order_by(Verification.transaction_date, Verification.verification_number).all()

        for ver in verifications:
            # #VER series number date "description"
            ver_date = ver.transaction_date.strftime("%Y%m%d")
            lines.append(f'#VER "{ver.series}" {ver.verification_number} {ver_date} "{ver.description}"')
            lines.append('{')

            # Transactions
            for line in ver.transaction_lines:
                account = line.account
                # In SIE4, debit is positive, credit is negative
                amount = line.debit - line.credit
                trans_desc = f' "{line.description}"' if line.description else ''
                lines.append(f'  #TRANS {account.account_number} {{}} {amount}{trans_desc}')

            lines.append('}')

    return '\n'.join(lines)
