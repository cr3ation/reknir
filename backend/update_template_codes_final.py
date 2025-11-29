import sys
sys.path.append('/app')

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.verification_template import VerificationTemplate

# Updated mapping following project standards (lowercase with underscores + VAT percentage)
CODE_MAPPING = {
    'PURCHASE_VAT': 'purchase_vat_25',
    'SALES_VAT': 'sales_vat_25', 
    'PAY_SUPPLIER': 'pay_supplier'
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
        
        print('✅ Template codes updated to follow project standards!')
        
    except Exception as e:
        print(f'❌ Error: {e}')
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    update_template_codes()
