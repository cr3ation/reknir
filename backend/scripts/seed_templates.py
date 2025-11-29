#!/usr/bin/env python3
"""
Seed script to create common Swedish verification templates
Run with: python seed_templates.py
"""

import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models.company import Company
from app.models.account import Account
from app.models.verification_template import VerificationTemplate, VerificationTemplateLine


# Common Swedish verification templates (names in English, descriptions in Swedish)
SWEDISH_TEMPLATES = [
    {
        "name": "Inköp med 25% moms",
        "description": "Inköp av varor/tjänster med 25% moms",
        "default_series": "A",
        "default_journal_text": "Inköp varor/tjänster med moms",
        "lines": [
            {"account_number": 4000, "formula": "{belopp} / 1.25", "description": "Inköp varor exkl moms", "sort_order": 1},
            {"account_number": 2640, "formula": "{belopp} * 0.2", "description": "Ingående moms 25%", "sort_order": 2},
            {"account_number": 2440, "formula": "-{belopp}", "description": "Leverantörsskuld", "sort_order": 3},
        ]
    },
    {
        "name": "Försäljning med 25% moms",
        "description": "Försäljning av varor/tjänster med 25% moms",
        "default_series": "A", 
        "default_journal_text": "Försäljning varor/tjänster med moms",
        "lines": [
            {"account_number": 1510, "formula": "{belopp}", "description": "Kundfordran", "sort_order": 1},
            {"account_number": 3001, "formula": "-{belopp} / 1.25", "description": "Försäljning 25% moms", "sort_order": 2},
            {"account_number": 2611, "formula": "-{belopp} * 0.2", "description": "Utgående moms 25%", "sort_order": 3},
        ]
    },
    {
        "name": "Leverantörsbetalning",
        "description": "Betalning av leverantörsfaktura",
        "default_series": "A",
        "default_journal_text": "Betalning leverantörsfaktura",
        "lines": [
            {"account_number": 2440, "formula": "{belopp}", "description": "Leverantörsskuld", "sort_order": 1},
            {"account_number": 1930, "formula": "-{belopp}", "description": "Bankkonto", "sort_order": 2},
        ]
    },
    {
        "name": "Inköp med 12% moms",
        "description": "Inköp av varor/tjänster med 12% moms",
        "default_series": "A",
        "default_journal_text": "Inköp varor/tjänster med 12% moms",
        "lines": [
            {"account_number": 4000, "formula": "{belopp} / 1.12", "description": "Inköp varor exkl moms", "sort_order": 1},
            {"account_number": 2640, "formula": "{belopp} * 0.107", "description": "Ingående moms 12%", "sort_order": 2},
            {"account_number": 2440, "formula": "-{belopp}", "description": "Leverantörsskuld", "sort_order": 3},
        ]
    },
    {
        "name": "Inköp med 6% moms",
        "description": "Inköp av varor/tjänster med 6% moms",
        "default_series": "A",
        "default_journal_text": "Inköp varor/tjänster med 6% moms",
        "lines": [
            {"account_number": 4000, "formula": "{belopp} / 1.06", "description": "Inköp varor exkl moms", "sort_order": 1},
            {"account_number": 2640, "formula": "{belopp} * 0.057", "description": "Ingående moms 6%", "sort_order": 2},
            {"account_number": 2440, "formula": "-{belopp}", "description": "Leverantörsskuld", "sort_order": 3},
        ]
    },
    {
        "name": "Kundbetalning", 
        "description": "Inbetalning från kund",
        "default_series": "A",
        "default_journal_text": "Inbetalning från kund",
        "lines": [
            {"account_number": 1930, "formula": "{belopp}", "description": "Bankkonto", "sort_order": 1},
            {"account_number": 1510, "formula": "-{belopp}", "description": "Kundfordran", "sort_order": 2},
        ]
    },
    {
        "name": "Lokalhyra",
        "description": "Månatlig hyra för lokaler",
        "default_series": "A",
        "default_journal_text": "Hyra för lokaler",
        "lines": [
            {"account_number": 5010, "formula": "{belopp}", "description": "Lokalhyra", "sort_order": 1},
            {"account_number": 1930, "formula": "-{belopp}", "description": "Bankkonto", "sort_order": 2},
        ]
    },
    {
        "name": "Löneutbetalning",
        "description": "Lön och sociala avgifter (förenklad)",
        "default_series": "A",
        "default_journal_text": "Löneutbetalning med avgifter",
        "lines": [
            {"account_number": 7210, "formula": "{belopp} * 0.6", "description": "Löner", "sort_order": 1},
            {"account_number": 7510, "formula": "{belopp} * 0.4", "description": "Sociala avgifter", "sort_order": 2},
            {"account_number": 1930, "formula": "-{belopp}", "description": "Bankkonto", "sort_order": 3},
        ]
    }
]


def find_account_by_number(db: Session, company_id: int, account_number: int) -> Account:
    """Find account by account number for a specific company"""
    account = db.query(Account).filter(
        Account.company_id == company_id,
        Account.account_number == account_number
    ).first()
    
    if not account:
        raise ValueError(f"Account {account_number} not found for company {company_id}")
    
    return account


def create_templates_for_company(db: Session, company_id: int):
    """Create all templates for a specific company"""
    print(f"Creating templates for company {company_id}...")
    
    for template_data in SWEDISH_TEMPLATES:
        # Check if template already exists
        existing = db.query(VerificationTemplate).filter(
            VerificationTemplate.company_id == company_id,
            VerificationTemplate.name == template_data["name"]
        ).first()
        
        if existing:
            print(f"  Template {template_data['name']} already exists, skipping...")
            continue
        
        # Create template
        template = VerificationTemplate(
            company_id=company_id,
            name=template_data["name"],
            description=template_data["description"],
            default_series=template_data["default_series"],
            default_journal_text=template_data["default_journal_text"]
        )
        
        db.add(template)
        db.flush()  # Get template ID
        
        # Create template lines
        for line_data in template_data["lines"]:
            try:
                account = find_account_by_number(db, company_id, line_data["account_number"])
                
                line = VerificationTemplateLine(
                    template_id=template.id,
                    account_id=account.id,
                    formula=line_data["formula"],
                    description=line_data["description"],
                    sort_order=line_data["sort_order"]
                )
                
                db.add(line)
                
            except ValueError as e:
                print(f"    Warning: {e} - skipping line")
                continue
        
        print(f"  Created template: {template_data['name']}")
    
    db.commit()
    print(f"Finished creating templates for company {company_id}")


def main():
    """Main function to seed templates for all companies"""
    db = SessionLocal()
    
    try:
        # Get all companies
        companies = db.query(Company).all()
        
        if not companies:
            print("No companies found. Please create a company first.")
            return
        
        print(f"Found {len(companies)} companies")
        
        for company in companies:
            print(f"\n--- Company: {company.name} ({company.org_number}) ---")
            create_templates_for_company(db, company.id)
        
        print("\n✅ Template seeding completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()