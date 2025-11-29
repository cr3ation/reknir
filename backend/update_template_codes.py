import sys
sys.path.append('/app')

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.verification_template import VerificationTemplate

# Mapping from Swedish to English codes
CODE_MAPPING = {
    'INKOP_MOMS': 'PURCHASE_VAT',
    'FORSALJNING_MOMS': 'SALES_VAT', 
    'BETALNING_LEV': 'PAY_SUPPLIER'
}

def update_template_codes():
    db = SessionLocal()
    
    try:
        for old_code, new_code in CODE_MAPPING.items():
            template = db.query(VerificationTemplate).filter(
                VerificationTemplate.code == old_code
            ).first()
            
            if template:
                print(f'Updating {old_code} -> {new_code}')
                template.code = new_code
                db.commit()
            else:
                print(f'Template {old_code} not found')
        
        print('✅ Template codes updated successfully!')
        
    except Exception as e:
        print(f'❌ Error: {e}')
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    update_template_codes()
