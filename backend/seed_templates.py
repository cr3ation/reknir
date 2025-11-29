import sys
sys.path.append('/app')

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.company import Company  
from app.models.account import Account
from app.models.verification_template import VerificationTemplate, VerificationTemplateLine

# Common Swedish verification templates
SWEDISH_TEMPLATES = [
    {
        'name': 'Inköp med 25% moms',
        'description': 'Inköp av varor/tjänster med 25% moms',
        'default_series': 'A',
        'default_journal_text': 'Inköp varor/tjänster med moms',
        'lines': [
            {'account_number': 4000, 'formula': '{belopp} / 1.25', 'description': 'Inköp varor exkl moms', 'sort_order': 1},
            {'account_number': 2640, 'formula': '{belopp} * 0.2', 'description': 'Ingående moms 25%', 'sort_order': 2},
            {'account_number': 2440, 'formula': '-{belopp}', 'description': 'Leverantörsskuld', 'sort_order': 3},
        ]
    },
    {
        'name': 'Försäljning med 25% moms', 
        'description': 'Försäljning av varor/tjänster med 25% moms',
        'default_series': 'A',
        'default_journal_text': 'Försäljning varor/tjänster med moms',
        'lines': [
            {'account_number': 1510, 'formula': '{belopp}', 'description': 'Kundfordran', 'sort_order': 1},
            {'account_number': 3001, 'formula': '-{belopp} / 1.25', 'description': 'Försäljning 25% moms', 'sort_order': 2},
            {'account_number': 2611, 'formula': '-{belopp} * 0.2', 'description': 'Utgående moms 25%', 'sort_order': 3},
        ]
    },
    {
        'code': 'BETALNING_LEV',
        'description': 'Betalning till leverantör',
        'default_series': 'A',
        'default_journal_text': 'Betalning leverantörsfaktura',
        'lines': [
            {'account_number': 2440, 'formula': '{belopp}', 'description': 'Leverantörsskuld', 'sort_order': 1},
            {'account_number': 1930, 'formula': '-{belopp}', 'description': 'Bankkonto', 'sort_order': 2},
        ]
    }
]

def find_account_by_number(db: Session, company_id: int, account_number: int):
    account = db.query(Account).filter(
        Account.company_id == company_id,
        Account.account_number == account_number
    ).first()
    
    if not account:
        raise ValueError(f'Account {account_number} not found for company {company_id}')
    
    return account

def create_templates_for_company(db: Session, company_id: int):
    print(f'Creating templates for company {company_id}...')
    
    for template_data in SWEDISH_TEMPLATES:
        # Check if template already exists
        existing = db.query(VerificationTemplate).filter(
            VerificationTemplate.company_id == company_id,
            VerificationTemplate.name == template_data['name']
        ).first()
        
        if existing:
            print(f'  Template {template_data["name"]} already exists, skipping...')
            continue
        
        # Create template
        template = VerificationTemplate(
            company_id=company_id,
            name=template_data['name'],
            description=template_data['description'],
            default_series=template_data['default_series'],
            default_journal_text=template_data['default_journal_text']
        )
        
        db.add(template)
        db.flush()  # Get template ID
        
        # Create template lines
        for line_data in template_data['lines']:
            try:
                account = find_account_by_number(db, company_id, line_data['account_number'])
                
                line = VerificationTemplateLine(
                    template_id=template.id,
                    account_id=account.id,
                    formula=line_data['formula'],
                    description=line_data['description'],
                    sort_order=line_data['sort_order']
                )
                
                db.add(line)
                
            except ValueError as e:
                print(f'    Warning: {e} - skipping line')
                continue
        
        print(f'  Created template: {template_data["name"]}')
    
    db.commit()
    print(f'Finished creating templates for company {company_id}')

def main():
    db = SessionLocal()
    
    try:
        # Get all companies
        companies = db.query(Company).all()
        
        if not companies:
            print('No companies found. Please create a company first.')
            return
        
        print(f'Found {len(companies)} companies')
        
        for company in companies:
            print(f'--- Company: {company.name} ({company.org_number}) ---')
            create_templates_for_company(db, company.id)
        
        print('✅ Template seeding completed successfully!')
        
    except Exception as e:
        print(f'❌ Error: {e}')
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    main()
