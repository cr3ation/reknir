"""
CLI commands for Reknir
Run with: python -m app.cli <command>
"""

import json
import sys
from pathlib import Path

from app.database import SessionLocal
from app.models import Account, Company
from app.models.account import AccountType


def seed_bas_accounts(company_id: int):
    """
    Seed BAS 2024 kontoplan for a company

    Args:
        company_id: Company ID to seed accounts for
    """
    db = SessionLocal()

    try:
        # Check if company exists
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            print(f"Error: Company with ID {company_id} not found")
            print("Please create a company first via the API")
            return False

        # Check if accounts already exist
        existing_count = db.query(Account).filter(Account.company_id == company_id).count()
        if existing_count > 0:
            print(f"Warning: Company {company_id} already has {existing_count} accounts")
            response = input("Do you want to continue and add more accounts? (y/n): ")
            if response.lower() != "y":
                print("Aborted")
                return False

        # Read BAS accounts JSON
        json_path = Path(__file__).parent.parent.parent / "database" / "seeds" / "bas_accounts.json"

        if not json_path.exists():
            print(f"Error: BAS accounts file not found at {json_path}")
            return False

        with open(json_path, encoding="utf-8") as f:
            accounts_data = json.load(f)

        # Import accounts
        imported = 0
        skipped = 0

        for acc_data in accounts_data:
            # Check if account already exists
            existing = (
                db.query(Account)
                .filter(Account.company_id == company_id, Account.account_number == acc_data["account_number"])
                .first()
            )

            if existing:
                print(f"  Skipping {acc_data['account_number']} - {acc_data['name']} (already exists)")
                skipped += 1
                continue

            # Create account
            account = Account(
                company_id=company_id,
                account_number=acc_data["account_number"],
                name=acc_data["name"],
                description=acc_data.get("description"),
                account_type=AccountType(acc_data["account_type"]),
                opening_balance=0,
                current_balance=0,
                is_bas_account=True,
                active=True,
            )
            db.add(account)
            imported += 1
            print(f"  ✓ {acc_data['account_number']} - {acc_data['name']}")

        db.commit()

        print(f"\nSuccess! Imported {imported} BAS accounts for company '{company.name}'")
        if skipped > 0:
            print(f"Skipped {skipped} accounts that already existed")

        return True

    except Exception as e:
        db.rollback()
        print(f"Error: {str(e)}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        db.close()


def main():
    """Main CLI entry point"""
    if len(sys.argv) < 2:
        print("Reknir CLI")
        print("\nUsage: python -m app.cli <command> [args]")
        print("\nCommands:")
        print("  seed-bas [company_id]  - Import BAS 2024 kontoplan for a company")
        print("                           Default company_id: 1")
        print("\nExamples:")
        print("  python -m app.cli seed-bas")
        print("  python -m app.cli seed-bas 2")
        sys.exit(1)

    command = sys.argv[1]

    if command == "seed-bas":
        # Get company_id from args or default to 1
        company_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1

        print(f"Seeding BAS 2024 kontoplan for company ID {company_id}...")
        print()

        success = seed_bas_accounts(company_id)
        sys.exit(0 if success else 1)

    else:
        print(f"Unknown command: {command}")
        print("Run 'python -m app.cli' to see available commands")
        sys.exit(1)


if __name__ == "__main__":
    main()
