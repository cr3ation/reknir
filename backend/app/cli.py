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
from app.models.posting_template import PostingTemplate, PostingTemplateLine


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


def load_posting_templates():
    """Load posting templates from JSON file"""
    template_file = Path(__file__).parent.parent.parent / "database" / "seeds" / "posting_templates.json"
    with open(template_file, encoding="utf-8") as f:
        return json.load(f)


def seed_all(company_id: int):
    """
    Seed both BAS accounts and posting templates for a company

    Args:
        company_id: Company ID to seed for
    """
    print(f"Complete setup for company ID {company_id}")
    print("=" * 50)

    # Seed BAS accounts first
    print("1. Seeding BAS kontoplan...")
    bas_success = seed_bas_accounts(company_id)

    if not bas_success:
        print("ERROR: BAS seeding failed, aborting complete setup")
        return False

    print("SUCCESS: BAS kontoplan seeded successfully!")
    print()

    # Seed posting templates
    print("2. Seeding posting templates...")
    template_success = seed_posting_templates(company_id)

    if not template_success:
        print("ERROR: Template seeding failed")
        return False

    print("SUCCESS: Posting templates seeded successfully!")
    print()
    print("Complete setup finished! Your company is ready to use.")
    return True


def seed_posting_templates(company_id: int):
    """
    Seed Swedish posting templates for a company

    Args:
        company_id: Company ID to seed templates for
    """
    db = SessionLocal()

    try:
        # Check if company exists
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            print(f"Error: Company with ID {company_id} not found")
            print("Please create a company first via the API")
            return False

        print(f"Creating posting templates for company '{company.name}'...")

        created = 0
        skipped = 0

        templates = load_posting_templates()

        for template_data in templates:
            # Check if template already exists
            existing = (
                db.query(PostingTemplate)
                .filter(PostingTemplate.company_id == company_id, PostingTemplate.name == template_data["name"])
                .first()
            )

            if existing:
                print(f"  Skipping '{template_data['name']}' (already exists)")
                skipped += 1
                continue

            # Create template
            template = PostingTemplate(
                company_id=company_id,
                name=template_data["name"],
                description=template_data["description"],
                default_series=template_data["default_series"],
                default_journal_text=template_data["default_journal_text"],
            )

            db.add(template)
            db.flush()  # Get template ID

            # Create template lines
            for line_data in template_data["lines"]:
                try:
                    account = (
                        db.query(Account)
                        .filter(Account.company_id == company_id, Account.account_number == line_data["account_number"])
                        .first()
                    )

                    if not account:
                        print(f"    Warning: Account {line_data['account_number']} not found - skipping line")
                        continue

                    line = PostingTemplateLine(
                        template_id=template.id,
                        account_id=account.id,
                        formula=line_data["formula"],
                        description=line_data["description"],
                        sort_order=line_data["sort_order"],
                    )

                    db.add(line)

                except Exception as e:
                    print(f"    Warning: {e} - skipping line")
                    continue

            print(f"  ✓ {template_data['name']}")
            created += 1

        db.commit()

        print(f"\nSuccess! Created {created} posting templates for company '{company.name}'")
        if skipped > 0:
            print(f"Skipped {skipped} templates that already existed")

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
        print("  seed-bas [company_id]       - Import BAS 2024 kontoplan for a company")
        print("  seed-templates [company_id] - Import Swedish posting templates for a company")
        print("  seed-all [company_id]       - Import both BAS and templates (complete setup)")
        print("                                Default company_id: 1")
        print("\nExamples:")
        print("  python -m app.cli seed-bas")
        print("  python -m app.cli seed-templates")
        print("  python -m app.cli seed-all          # Complete setup")
        print("  python -m app.cli seed-bas 2")
        print("  python -m app.cli seed-templates 2")
        sys.exit(1)

    command = sys.argv[1]

    if command == "seed-bas":
        # Get company_id from args or default to 1
        company_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1

        print(f"Seeding BAS 2024 kontoplan for company ID {company_id}...")
        print()

        success = seed_bas_accounts(company_id)
        sys.exit(0 if success else 1)

    elif command == "seed-templates":
        # Get company_id from args or default to 1
        company_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1

        print(f"Seeding Swedish posting templates for company ID {company_id}...")
        print()

        success = seed_posting_templates(company_id)
        sys.exit(0 if success else 1)

    elif command == "seed-all":
        # Get company_id from args or default to 1
        company_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1

        success = seed_all(company_id)
        sys.exit(0 if success else 1)

    else:
        print(f"Unknown command: {command}")
        print("Run 'python -m app.cli' to see available commands")
        sys.exit(1)


if __name__ == "__main__":
    main()
