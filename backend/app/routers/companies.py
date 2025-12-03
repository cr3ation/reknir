from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import json
import os
import uuid
import shutil
from app.database import get_db
from app.models.company import Company
from app.models.account import Account
from app.models.default_account import DefaultAccount
from app.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate
from app.services import default_account_service

router = APIRouter()


@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(company: CompanyCreate, db: Session = Depends(get_db)):
    """Create a new company"""

    # Check if org_number already exists
    existing = db.query(Company).filter(Company.org_number == company.org_number).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Company with org number {company.org_number} already exists"
        )

    # Create company
    db_company = Company(**company.model_dump())
    db.add(db_company)
    db.commit()
    db.refresh(db_company)

    return db_company


@router.get("/", response_model=List[CompanyResponse])
def list_companies(db: Session = Depends(get_db)):
    """List all companies"""
    companies = db.query(Company).all()
    return companies


@router.get("/bas-accounts", status_code=status.HTTP_200_OK)
def get_bas_accounts():
    """Get all BAS 2024 reference accounts"""
    bas_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'bas_2024.json')
    if not os.path.exists(bas_file):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BAS 2024 data file not found"
        )

    with open(bas_file, 'r', encoding='utf-8') as f:
        bas_data = json.load(f)

    return bas_data


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(company_id: int, db: Session = Depends(get_db)):
    """Get a specific company"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )
    return company


@router.patch("/{company_id}", response_model=CompanyResponse)
def update_company(company_id: int, company_update: CompanyUpdate, db: Session = Depends(get_db)):
    """Update a company"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )

    # Update fields
    update_data = company_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    db.commit()
    db.refresh(company)
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, db: Session = Depends(get_db)):
    """Delete a company (WARNING: deletes all associated data)"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )

    db.delete(company)
    db.commit()
    return None


@router.post("/{company_id}/seed-bas", status_code=status.HTTP_200_OK)
def seed_bas_accounts(
    company_id: int,
    fiscal_year_id: int = Query(..., description="Fiscal Year ID to seed accounts for"),
    db: Session = Depends(get_db)
):
    """Seed BAS 2024 kontoplan for a fiscal year"""
    from app.models.fiscal_year import FiscalYear

    # Check if company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )

    # Check if fiscal year exists and belongs to this company
    fiscal_year = db.query(FiscalYear).filter(FiscalYear.id == fiscal_year_id).first()
    if not fiscal_year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fiscal year {fiscal_year_id} not found"
        )
    if fiscal_year.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fiscal year {fiscal_year_id} does not belong to company {company_id}"
        )

    # Check if fiscal year already has accounts
    existing_count = db.query(Account).filter(Account.fiscal_year_id == fiscal_year_id).count()
    if existing_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fiscal year already has {existing_count} accounts. Delete them first if you want to re-seed."
        )

    # Load BAS accounts from JSON
    bas_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'bas_2024.json')
    if not os.path.exists(bas_file):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BAS 2024 data file not found"
        )

    with open(bas_file, 'r', encoding='utf-8') as f:
        bas_data = json.load(f)

    # Create accounts
    created_accounts = []
    for account_data in bas_data['accounts']:
        account = Account(
            company_id=company_id,
            fiscal_year_id=fiscal_year_id,
            account_number=account_data['account_number'],
            name=account_data['name'],
            account_type=account_data['account_type'],
            description=account_data.get('description'),
            active=True
        )
        db.add(account)
        created_accounts.append(account)

    db.commit()

    # Also initialize default account mappings
    default_account_service.initialize_default_accounts_from_existing(db, company_id, fiscal_year_id)

    defaults_count = db.query(DefaultAccount).filter(
        DefaultAccount.company_id == company_id
    ).count()

    return {
        "message": f"Successfully seeded {len(created_accounts)} BAS 2024 accounts for fiscal year {fiscal_year.label} and configured {defaults_count} default account mappings",
        "fiscal_year_id": fiscal_year_id,
        "fiscal_year_label": fiscal_year.label,
        "accounts_created": len(created_accounts),
        "default_accounts_configured": defaults_count
    }


@router.post("/{company_id}/seed-templates", status_code=status.HTTP_200_OK)
def seed_posting_templates(company_id: int, db: Session = Depends(get_db)):
    """Seed Swedish posting templates for a company"""
    from app.cli import load_posting_templates
    from app.models.posting_template import PostingTemplate, PostingTemplateLine
    from app.models.fiscal_year import FiscalYear

    # Check if company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )

    # Get the first fiscal year for this company to find accounts
    # Posting templates are company-wide but need to reference accounts from a fiscal year
    fiscal_year = db.query(FiscalYear).filter(
        FiscalYear.company_id == company_id
    ).order_by(FiscalYear.start_date).first()

    if not fiscal_year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company must have at least one fiscal year with accounts before seeding templates"
        )

    # Check if templates already exist
    existing_count = db.query(PostingTemplate).filter(PostingTemplate.company_id == company_id).count()
    if existing_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Company already has {existing_count} posting templates. Delete them first if you want to re-seed."
        )

    try:
        templates_data = load_posting_templates()
        created_templates = []
        
        for template_data in templates_data:
            # Create template
            template = PostingTemplate(
                company_id=company_id,
                name=template_data['name'],
                description=template_data['description'],
                default_series=template_data['default_series'],
                default_journal_text=template_data['default_journal_text'],
                sort_order=template_data.get('sort_order', 999)
            )
            
            db.add(template)
            db.flush()  # Get template ID
            
            # Create template lines
            for line_data in template_data['lines']:
                account = db.query(Account).filter(
                    Account.company_id == company_id,
                    Account.fiscal_year_id == fiscal_year.id,
                    Account.account_number == line_data['account_number']
                ).first()

                if account:  # Only create line if account exists
                    line = PostingTemplateLine(
                        template_id=template.id,
                        account_id=account.id,
                        formula=line_data['formula'],
                        description=line_data['description'],
                        sort_order=line_data['sort_order']
                    )
                    db.add(line)
            
            created_templates.append(template)
        
        db.commit()
        
        return {
            "message": f"Successfully seeded {len(created_templates)} posting templates",
            "templates_created": len(created_templates)
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed posting templates: {str(e)}"
        )


@router.post("/{company_id}/initialize-defaults", status_code=status.HTTP_200_OK)
def initialize_default_accounts(company_id: int, db: Session = Depends(get_db)):
    """
    Initialize default account mappings for a company based on existing accounts.
    This is useful after importing SIE4 or when setting up an existing company.
    """
    from app.models.fiscal_year import FiscalYear

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )

    # Get the first fiscal year for this company
    fiscal_year = db.query(FiscalYear).filter(
        FiscalYear.company_id == company_id
    ).order_by(FiscalYear.start_date).first()

    if not fiscal_year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company must have at least one fiscal year before initializing defaults"
        )

    # Initialize defaults
    default_account_service.initialize_default_accounts_from_existing(db, company_id, fiscal_year.id)

    # Count configured defaults
    defaults_count = db.query(DefaultAccount).filter(
        DefaultAccount.company_id == company_id
    ).count()

    return {
        "message": f"Successfully initialized {defaults_count} default account mappings",
        "default_accounts_configured": defaults_count
    }


@router.post("/{company_id}/logo", response_model=CompanyResponse)
async def upload_company_logo(
    company_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a company logo (PNG or JPG only)"""
    # Check if company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )

    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image"
        )
    
    allowed_types = ['image/png', 'image/jpeg', 'image/jpg']
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PNG and JPG files are allowed"
        )

    # Validate file size (5MB max)
    file_size = 0
    content = await file.read()
    file_size = len(content)
    if file_size > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 5MB"
        )

    # Create uploads directory if it doesn't exist
    upload_dir = "/app/uploads/logos"
    os.makedirs(upload_dir, exist_ok=True)

    # Generate unique filename
    file_extension = file.filename.split('.')[-1].lower()
    unique_filename = f"{company_id}_{uuid.uuid4().hex}.{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)

    # Remove old logo file if exists
    if company.logo_filename:
        old_file_path = os.path.join(upload_dir, company.logo_filename)
        if os.path.exists(old_file_path):
            os.remove(old_file_path)

    # Save new file
    with open(file_path, "wb") as buffer:
        buffer.write(content)

    # Update company record
    company.logo_filename = unique_filename
    db.commit()
    db.refresh(company)

    return company


@router.get("/{company_id}/logo")
async def get_company_logo(company_id: int, db: Session = Depends(get_db)):
    """Download company logo"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )

    if not company.logo_filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No logo found for this company"
        )

    file_path = f"/app/uploads/logos/{company.logo_filename}"
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Logo file not found on disk"
        )

    # Determine media type from file extension
    file_extension = company.logo_filename.split('.')[-1].lower()
    media_type = "image/png" if file_extension == "png" else "image/jpeg"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=f"company_{company_id}_logo.{file_extension}"
    )


@router.delete("/{company_id}/logo", response_model=CompanyResponse)
async def delete_company_logo(company_id: int, db: Session = Depends(get_db)):
    """Delete company logo"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )

    if not company.logo_filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No logo found for this company"
        )

    # Remove file from disk
    file_path = f"/app/uploads/logos/{company.logo_filename}"
    if os.path.exists(file_path):
        os.remove(file_path)

    # Clear logo_filename from database
    company.logo_filename = None
    db.commit()
    db.refresh(company)

    return company
