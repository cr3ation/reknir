"""
SIE4 Import/Export Service

SIE (Standard Import Export) is the Swedish standard for importing/exporting accounting data.
This service handles SIE4 format, which includes:
- Chart of accounts (#KONTO)
- Verifications and transactions (#VER, #TRANS)
- Balances (#IB, #UB)
- Company info (#FNAMN, #ORGNR, #RAR)
"""

import re
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.models.company import Company
from app.models.fiscal_year import FiscalYear
from app.models.verification import TransactionLine, Verification
from app.services import default_account_service


def _parse_rar_from_file(file_content: str) -> tuple[date, date] | None:
    """
    Parse #RAR 0 (current fiscal year) from SIE4 file content.

    Returns:
        Tuple of (start_date, end_date) if found, None otherwise
    """
    for line in file_content.splitlines():
        command, args = _parse_sie_line(line)
        if command == "RAR" and len(args) >= 3 and args[0] == "0":
            try:
                start = datetime.strptime(args[1], "%Y%m%d").date()
                end = datetime.strptime(args[2], "%Y%m%d").date()
                return (start, end)
            except ValueError:
                return None
    return None


def _check_overlapping_fiscal_years(
    db: Session, company_id: int, start_date: date, end_date: date, exclude_fiscal_year_id: int | None = None
) -> list[tuple[int, date, date]]:
    """
    Check if the given date range overlaps with any existing fiscal years.

    Returns:
        List of tuples (fiscal_year_id, start_date, end_date) for overlapping years
    """
    fiscal_years = db.query(FiscalYear).filter(FiscalYear.company_id == company_id).all()

    overlapping = []
    for fy in fiscal_years:
        if exclude_fiscal_year_id and fy.id == exclude_fiscal_year_id:
            continue
        # Check for overlap: periods overlap if one starts before the other ends
        if start_date <= fy.end_date and end_date >= fy.start_date:
            overlapping.append((fy.id, fy.start_date, fy.end_date))

    return overlapping


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


def _parse_sie_line(line: str) -> tuple[str, list[str]]:
    """
    Parse a SIE4 line into command and arguments.

    Example:
        '#KONTO 1510 "Kundfordringar"' -> ('KONTO', ['1510', 'Kundfordringar'])
        '#VER "A" 1 20241109 "Description"' -> ('VER', ['A', '1', '20241109', 'Description'])
    """
    line = line.strip()
    if not line or line.startswith("#"):
        # Skip comments and empty lines (but not commands starting with #)
        if not line.startswith("#") or line == "#":
            return "", []

    # Extract command
    match = re.match(r"#(\w+)\s+(.*)", line)
    if not match:
        return "", []

    command = match.group(1)
    rest = match.group(2)

    # Parse arguments - handle quoted strings and numbers
    args = []
    current_arg = ""
    in_quotes = False

    for char in rest:
        if char == '"':
            in_quotes = not in_quotes
        elif char in (" ", "\t") and not in_quotes:
            if current_arg:
                args.append(current_arg)
                current_arg = ""
        elif char == "{" or char == "}":
            # Skip transaction delimiters
            continue
        else:
            current_arg += char

    if current_arg:
        args.append(current_arg)

    return command, args


def preview_sie4(db: Session, company_id: int, file_content: str) -> dict:
    """
    Preview SIE4 file import without making changes.

    Analyzes the file and returns what would happen if imported.
    This is a read-only operation.

    Returns:
        Dict with preview information:
        - can_import: bool (False if there are blocking errors)
        - fiscal_year_start/end: dates from #RAR 0
        - fiscal_year_exists: bool
        - existing_fiscal_year_id: int or None
        - will_create_fiscal_year: bool
        - accounts_count: int
        - verifications_count: int
        - blocking_errors: list[str]
        - warnings: list[str]
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return {
            "can_import": False,
            "fiscal_year_start": None,
            "fiscal_year_end": None,
            "fiscal_year_exists": False,
            "existing_fiscal_year_id": None,
            "will_create_fiscal_year": False,
            "accounts_count": 0,
            "verifications_count": 0,
            "blocking_errors": [f"Företag med ID {company_id} hittades inte"],
            "warnings": [],
        }

    blocking_errors = []
    warnings = []

    # Parse #RAR 0 to get fiscal year dates
    rar_dates = _parse_rar_from_file(file_content)
    if not rar_dates:
        blocking_errors.append("SIE4-filen saknar räkenskapsårsinformation (#RAR 0)")
        return {
            "can_import": False,
            "fiscal_year_start": None,
            "fiscal_year_end": None,
            "fiscal_year_exists": False,
            "existing_fiscal_year_id": None,
            "will_create_fiscal_year": False,
            "accounts_count": 0,
            "verifications_count": 0,
            "blocking_errors": blocking_errors,
            "warnings": warnings,
        }

    rar_start, rar_end = rar_dates

    # Validate dates
    if rar_end < rar_start:
        blocking_errors.append(f"Ogiltigt räkenskapsår: slutdatum ({rar_end}) är före startdatum ({rar_start})")

    # Check if fiscal year already exists (exact match)
    existing_fy = (
        db.query(FiscalYear)
        .filter(
            FiscalYear.company_id == company_id,
            FiscalYear.start_date == rar_start,
            FiscalYear.end_date == rar_end,
        )
        .first()
    )

    fiscal_year_exists = existing_fy is not None
    existing_fiscal_year_id = existing_fy.id if existing_fy else None
    will_create_fiscal_year = not fiscal_year_exists

    # Check for overlapping fiscal years (if we need to create one)
    if will_create_fiscal_year:
        overlapping = _check_overlapping_fiscal_years(db, company_id, rar_start, rar_end)
        if overlapping:
            # Get labels for better error message
            for fy_id, start, end in overlapping:
                fy = db.query(FiscalYear).filter(FiscalYear.id == fy_id).first()
                label = fy.label if fy else f"{start.year}"
                blocking_errors.append(
                    f"Räkenskapsåret ({rar_start} - {rar_end}) överlappar med befintligt: {label} ({start} - {end})"
                )

    # Count accounts and verifications in the file
    accounts_count = 0
    verifications_count = 0
    existing_account_numbers = set()
    accounts_in_file = set()

    # Get existing accounts for this fiscal year if it exists
    if fiscal_year_exists:
        existing_accounts = (
            db.query(Account.account_number)
            .filter(Account.company_id == company_id, Account.fiscal_year_id == existing_fiscal_year_id)
            .all()
        )
        existing_account_numbers = {a.account_number for a in existing_accounts}

    for line in file_content.splitlines():
        command, args = _parse_sie_line(line)

        if command == "KONTO" and len(args) >= 2:
            try:
                account_number = int(args[0])
                accounts_in_file.add(account_number)
                accounts_count += 1
            except ValueError:
                pass

        elif command == "VER" and len(args) >= 3:
            verifications_count += 1

    # Check for accounts that will be updated vs created
    if existing_account_numbers:
        accounts_to_update = accounts_in_file & existing_account_numbers
        if accounts_to_update:
            warnings.append(f"{len(accounts_to_update)} konton finns redan och kommer uppdateras")

    return {
        "can_import": len(blocking_errors) == 0,
        "fiscal_year_start": rar_start,
        "fiscal_year_end": rar_end,
        "fiscal_year_exists": fiscal_year_exists,
        "existing_fiscal_year_id": existing_fiscal_year_id,
        "will_create_fiscal_year": will_create_fiscal_year,
        "accounts_count": accounts_count,
        "verifications_count": verifications_count,
        "blocking_errors": blocking_errors,
        "warnings": warnings,
    }


def import_sie4(
    db: Session, company_id: int, file_content: str, fiscal_year_id: int | None = None
) -> dict[str, any]:
    """
    Import SIE4 file content into the database.

    The fiscal year is determined from the file's #RAR 0 entry. If a matching
    fiscal year exists, it will be used. If not, a new fiscal year will be created.

    Args:
        db: Database session
        company_id: Company ID to import to
        file_content: SIE4 file content as string
        fiscal_year_id: Optional fiscal year ID (if None, uses #RAR 0 from file)

    Returns a dict with import statistics:
    - accounts_created: number of accounts created
    - accounts_updated: number of accounts updated
    - verifications_created: number of verifications created
    - verifications_skipped: number of verifications skipped
    - default_accounts_configured: number of default accounts configured
    - fiscal_year_id: ID of the fiscal year used/created
    - fiscal_year_created: whether a new fiscal year was created
    - errors: list of error messages encountered
    - warnings: list of warning messages
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise ValueError(f"Company {company_id} not found")

    stats = {
        "accounts_created": 0,
        "accounts_updated": 0,
        "verifications_created": 0,
        "verifications_skipped": 0,
        "default_accounts_configured": 0,
        "fiscal_year_id": None,
        "fiscal_year_created": False,
        "errors": [],
        "warnings": [],
    }

    # Parse #RAR 0 from file to get fiscal year dates
    rar_dates = _parse_rar_from_file(file_content)
    if not rar_dates:
        raise ValueError("SIE4-filen saknar räkenskapsårsinformation (#RAR 0)")

    rar_start, rar_end = rar_dates

    # Validate dates
    if rar_end < rar_start:
        raise ValueError(f"Ogiltigt räkenskapsår: slutdatum ({rar_end}) är före startdatum ({rar_start})")

    # Find or create fiscal year based on #RAR 0
    if fiscal_year_id:
        # Use provided fiscal year but validate it matches #RAR 0
        fiscal_year = db.query(FiscalYear).filter(FiscalYear.id == fiscal_year_id).first()
        if not fiscal_year:
            raise ValueError(f"Fiscal year {fiscal_year_id} not found")
        if fiscal_year.company_id != company_id:
            raise ValueError(f"Fiscal year {fiscal_year_id} does not belong to company {company_id}")
        if rar_start != fiscal_year.start_date or rar_end != fiscal_year.end_date:
            raise ValueError(
                f"SIE4-filens räkenskapsår ({rar_start} - {rar_end}) matchar inte valt räkenskapsår "
                f"({fiscal_year.start_date} - {fiscal_year.end_date})"
            )
    else:
        # Find existing fiscal year matching #RAR 0 dates
        fiscal_year = (
            db.query(FiscalYear)
            .filter(
                FiscalYear.company_id == company_id,
                FiscalYear.start_date == rar_start,
                FiscalYear.end_date == rar_end,
            )
            .first()
        )

        if not fiscal_year:
            # Check for overlapping fiscal years before creating
            overlapping = _check_overlapping_fiscal_years(db, company_id, rar_start, rar_end)
            if overlapping:
                overlap_info = []
                for fy_id, start, end in overlapping:
                    fy = db.query(FiscalYear).filter(FiscalYear.id == fy_id).first()
                    label = fy.label if fy else f"{start.year}"
                    overlap_info.append(f"{label} ({start} - {end})")
                raise ValueError(
                    f"Räkenskapsåret ({rar_start} - {rar_end}) överlappar med befintliga: {', '.join(overlap_info)}"
                )

            # Create new fiscal year
            fiscal_year = FiscalYear(
                company_id=company_id,
                year=rar_start.year,
                label=str(rar_start.year),
                start_date=rar_start,
                end_date=rar_end,
                is_closed=False,
            )
            db.add(fiscal_year)
            db.flush()  # Get the ID
            stats["fiscal_year_created"] = True

    stats["fiscal_year_id"] = fiscal_year.id
    fiscal_year_id = fiscal_year.id  # Update variable for use in rest of function

    lines = file_content.splitlines()  # Handle all line ending types
    accounts_cache = {}  # Cache account number -> Account object
    current_verification = None
    verifications_to_create = []  # Store verifications to create after parsing
    commands_parsed = 0  # Track how many commands we successfully parsed

    for line in lines:
        command, args = _parse_sie_line(line)

        if not command:
            continue

        commands_parsed += 1

        if command == "KONTO":
            # #KONTO account_number "name"
            if len(args) >= 2:
                try:
                    account_number = int(args[0])
                    account_name = args[1]

                    # Check if account exists in this fiscal year
                    existing = (
                        db.query(Account)
                        .filter(
                            Account.company_id == company_id,
                            Account.fiscal_year_id == fiscal_year_id,
                            Account.account_number == account_number,
                        )
                        .first()
                    )

                    if existing:
                        # Update name if different
                        if existing.name != account_name:
                            existing.name = account_name
                            stats["accounts_updated"] += 1
                        accounts_cache[account_number] = existing
                    else:
                        # Create new account for this fiscal year
                        account_type = _determine_account_type(account_number)
                        new_account = Account(
                            company_id=company_id,
                            fiscal_year_id=fiscal_year_id,
                            account_number=account_number,
                            name=account_name,
                            account_type=account_type,
                            is_bas_account=False,  # Imported accounts are not necessarily BAS
                        )
                        db.add(new_account)
                        db.flush()  # Get the ID
                        accounts_cache[account_number] = new_account
                        stats["accounts_created"] += 1
                except (ValueError, IndexError) as e:
                    stats["errors"].append(f"Failed to parse KONTO line: {e}")

        elif command == "IB":
            # #IB year_index account_number opening_balance
            # year_index: 0 = current fiscal year, -1 = previous year, etc.
            if len(args) >= 3:
                year_index = int(args[0])
                if year_index == 0:  # Only import current year's balances
                    account_number = int(args[1])
                    balance = Decimal(args[2])

                    if account_number in accounts_cache:
                        account = accounts_cache[account_number]
                        account.opening_balance = balance
                        account.current_balance = balance  # Default, may be overwritten by UB

        elif command == "UB":
            # #UB year_index account_number closing_balance
            # year_index: 0 = current fiscal year, -1 = previous year, etc.
            if len(args) >= 3:
                year_index = int(args[0])
                if year_index == 0:  # Only import current year's balances
                    account_number = int(args[1])
                    balance = Decimal(args[2])

                    if account_number in accounts_cache:
                        account = accounts_cache[account_number]
                        account.current_balance = balance

        elif command == "VER":
            # Save previous verification if exists
            if current_verification and current_verification["lines"]:
                verifications_to_create.append(current_verification)

            # #VER series verification_number transaction_date "description"
            # Transactions follow in subsequent #TRANS lines until closing }
            if len(args) >= 3:
                try:
                    # Handle verification number - might be string or int
                    ver_number = args[1]
                    if isinstance(ver_number, str) and not ver_number.isdigit():
                        # If it contains non-digits, try to extract digits
                        import re

                        digit_match = re.search(r"\d+", ver_number)
                        if digit_match:
                            ver_number = digit_match.group()

                    current_verification = {
                        "series": args[0],
                        "number": int(ver_number),
                        "date": args[2],
                        "description": args[3] if len(args) > 3 else "",
                        "lines": [],
                    }
                except (ValueError, IndexError) as e:
                    stats["errors"].append(f"Failed to parse VER line: {e}")
                    current_verification = None

        elif command == "TRANS":
            # #TRANS account_number {object_list} amount [transaction_date] ["description"]
            if current_verification and len(args) >= 2:
                try:
                    account_number = int(args[0])

                    # Parse amount - can be with or without object list {}
                    amount_str = args[1]
                    if amount_str == "{}" and len(args) >= 3:
                        amount_str = args[2]

                    amount = Decimal(amount_str)
                    description = ""
                    if len(args) > 2:
                        # Last argument might be description
                        last_arg = args[-1]
                        if not last_arg.replace(".", "").replace("-", "").isdigit():
                            description = last_arg

                    current_verification["lines"].append(
                        {"account_number": account_number, "amount": amount, "description": description}
                    )
                except (ValueError, IndexError, KeyError) as e:
                    stats["errors"].append(f"Failed to parse TRANS line: {e}")

    # Don't forget the last verification
    if current_verification and current_verification["lines"]:
        verifications_to_create.append(current_verification)

    # Check if any commands were parsed
    if commands_parsed == 0:
        stats["errors"].append(
            f"No SIE4 commands found in file. File may be empty or have incorrect format. Total lines: {len(lines)}"
        )

    # Commit account changes
    db.commit()

    # Reload accounts cache from database to get IDs for this fiscal year
    all_accounts = (
        db.query(Account).filter(Account.company_id == company_id, Account.fiscal_year_id == fiscal_year_id).all()
    )
    accounts_by_number = {acc.account_number: acc for acc in all_accounts}

    # Create verifications
    skipped_duplicates = 0
    skipped_missing_accounts = []

    for ver_data in verifications_to_create:
        try:
            # Parse date
            date_str = ver_data["date"]
            if len(date_str) == 8:  # YYYYMMDD format
                transaction_date = datetime.strptime(date_str, "%Y%m%d").date()
            else:
                # Skip if date format is invalid
                stats["warnings"].append(
                    f"Invalid date format for verification {ver_data.get('series', '?')}-{ver_data.get('number', '?')}: {date_str}"
                )
                continue

            # Check if verification already exists (same series, number, and date)
            existing_ver = (
                db.query(Verification)
                .filter(
                    Verification.company_id == company_id,
                    Verification.series == ver_data["series"],
                    Verification.verification_number == ver_data["number"],
                    Verification.transaction_date == transaction_date,
                )
                .first()
            )

            if existing_ver:
                # Skip duplicate verifications
                skipped_duplicates += 1
                continue

            # Check for missing accounts BEFORE creating verification
            # Skip entire verification if any account is missing to prevent unbalanced entries
            missing_accounts_in_ver = []
            for line_data in ver_data["lines"]:
                account_number = line_data["account_number"]
                if account_number not in accounts_by_number:
                    missing_accounts_in_ver.append(account_number)
                    if account_number not in skipped_missing_accounts:
                        skipped_missing_accounts.append(account_number)

            if missing_accounts_in_ver:
                # Skip entire verification to prevent unbalanced entries
                stats["verifications_skipped"] += 1
                stats["warnings"].append(
                    f"Verifikation {ver_data['series']}-{ver_data['number']} hoppades över - "
                    f"saknade konton: {', '.join(map(str, sorted(missing_accounts_in_ver)))}"
                )
                continue

            # Create verification (all accounts exist)
            verification = Verification(
                company_id=company_id,
                fiscal_year_id=fiscal_year_id,
                series=ver_data["series"],
                verification_number=ver_data["number"],
                transaction_date=transaction_date,
                description=ver_data["description"],
            )
            db.add(verification)
            db.flush()  # Get the ID

            # Create transaction lines
            for line_data in ver_data["lines"]:
                account_number = line_data["account_number"]
                account = accounts_by_number[account_number]
                amount = line_data["amount"]

                # In SIE4: positive amount = debit, negative amount = credit
                debit = amount if amount > 0 else Decimal(0)
                credit = -amount if amount < 0 else Decimal(0)

                trans_line = TransactionLine(
                    verification_id=verification.id,
                    account_id=account.id,
                    debit=debit,
                    credit=credit,
                    description=line_data["description"],
                )
                db.add(trans_line)

            stats["verifications_created"] += 1

        except Exception as e:
            # Log error but continue with other verifications
            stats["errors"].append(
                f"Error creating verification {ver_data.get('series', '?')}-{ver_data.get('number', '?')}: {str(e)}"
            )
            continue

    # Add summary warnings
    if skipped_duplicates > 0:
        stats["warnings"].append(f"Hoppade över {skipped_duplicates} duplicerade verifikationer")
    if skipped_missing_accounts:
        stats["warnings"].append(
            f"Saknade konton (totalt): {', '.join(map(str, sorted(skipped_missing_accounts)))}"
        )

    # Commit verifications
    db.commit()

    # Initialize default account mappings based on imported accounts
    default_account_service.initialize_default_accounts_from_existing(db, company_id, fiscal_year_id)

    # Count how many defaults were configured
    from app.models.default_account import DefaultAccount

    defaults_count = db.query(DefaultAccount).filter(DefaultAccount.company_id == company_id).count()
    stats["default_accounts_configured"] = defaults_count

    return stats


def export_sie4(db: Session, company_id: int, fiscal_year_id: int, include_verifications: bool = True) -> str:
    """
    Export company data to SIE4 format for a specific fiscal year.

    Args:
        db: Database session
        company_id: Company to export
        fiscal_year_id: Fiscal year to export
        include_verifications: Whether to include verifications (default True)

    Returns:
        SIE4 formatted string
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise ValueError(f"Company {company_id} not found")

    fiscal_year = db.query(FiscalYear).filter(FiscalYear.id == fiscal_year_id).first()
    if not fiscal_year:
        raise ValueError(f"Fiscal year {fiscal_year_id} not found")

    if fiscal_year.company_id != company_id:
        raise ValueError(f"Fiscal year {fiscal_year_id} does not belong to company {company_id}")

    lines = []

    # Header
    lines.append("#FLAGGA 0")
    lines.append('#PROGRAM "Reknir" "1.0"')
    lines.append("#FORMAT PC8")
    lines.append(f'#GEN {date.today().strftime("%Y%m%d")}')
    lines.append("#SIETYP 4")

    # Company info
    lines.append(f'#FNAMN "{company.name}"')
    lines.append(f'#ORGNR "{company.org_number}"')

    # Fiscal year
    lines.append(f'#RAR 0 {fiscal_year.start_date.strftime("%Y%m%d")} {fiscal_year.end_date.strftime("%Y%m%d")}')

    # Chart of accounts
    accounts = (
        db.query(Account)
        .filter(Account.company_id == company_id, Account.fiscal_year_id == fiscal_year_id, Account.active.is_(True))
        .order_by(Account.account_number)
        .all()
    )

    for account in accounts:
        lines.append(f'#KONTO {account.account_number} "{account.name}"')

        # Opening balance (if not zero)
        if account.opening_balance != 0:
            lines.append(f"#IB 0 {account.account_number} {account.opening_balance}")

        # Current balance (if different from opening)
        if account.current_balance != account.opening_balance:
            lines.append(f"#UB 0 {account.account_number} {account.current_balance}")

    # Verifications
    if include_verifications:
        verifications = (
            db.query(Verification)
            .filter(Verification.company_id == company_id, Verification.fiscal_year_id == fiscal_year_id)
            .order_by(Verification.transaction_date, Verification.verification_number)
            .all()
        )

        for ver in verifications:
            # #VER series number date "description"
            ver_date = ver.transaction_date.strftime("%Y%m%d")
            lines.append(f'#VER "{ver.series}" {ver.verification_number} {ver_date} "{ver.description}"')
            lines.append("{")

            # Transactions
            for line in ver.transaction_lines:
                account = line.account
                # In SIE4, debit is positive, credit is negative
                amount = line.debit - line.credit
                trans_desc = f' "{line.description}"' if line.description else ""
                lines.append(f"  #TRANS {account.account_number} {{}} {amount}{trans_desc}")

            lines.append("}")

    return "\n".join(lines)
