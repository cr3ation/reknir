import json
import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user, get_user_company_ids
from app.models.account import Account
from app.models.company import Company
from app.models.default_account import DefaultAccount
from app.models.user import CompanyUser, User
from app.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate
from app.services import default_account_service

router = APIRouter()


@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(
    company: CompanyCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """Create a new company"""

    # Check if org_number already exists
    existing = db.query(Company).filter(Company.org_number == company.org_number).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Company with org number {company.org_number} already exists",
        )

    # Create company
    db_company = Company(**company.model_dump())
    db.add(db_company)
    db.commit()
    db.refresh(db_company)

    # Auto-grant access to creator (if not admin)
    # Admins have access to all companies by default, but we can still add them for explicit tracking
    if not current_user.is_admin:
        company_user = CompanyUser(
            company_id=db_company.id, user_id=current_user.id, role="accountant", created_by=current_user.id
        )
        db.add(company_user)
        db.commit()

    return db_company


@router.get("/", response_model=list[CompanyResponse])
def list_companies(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """List companies user has access to"""
    # Get company IDs user has access to
    company_ids = get_user_company_ids(current_user, db)

    # Filter companies by accessible IDs
    companies = db.query(Company).filter(Company.id.in_(company_ids)).all()
    return companies


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(company_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Get a specific company"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company {company_id} not found")

    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if company_id not in company_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this company")

    return company


@router.patch("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: int,
    company_update: CompanyUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update a company"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company {company_id} not found")

    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if company_id not in company_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this company")

    # Update fields
    update_data = company_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    db.commit()
    db.refresh(company)
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """Delete a company (WARNING: deletes all associated data)"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company {company_id} not found")

    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if company_id not in company_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this company")

    db.delete(company)
    db.commit()
    return None


@router.post("/{company_id}/seed-bas", status_code=status.HTTP_200_OK)
def seed_bas_accounts(
    company_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """Seed BAS 2024 kontoplan for a company"""
    # Check if company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company {company_id} not found")

    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if company_id not in company_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this company")

    # Check if accounts already exist
    existing_count = db.query(Account).filter(Account.company_id == company_id).count()
    if existing_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Company already has {existing_count} accounts. Delete them first if you want to re-seed.",
        )

    # Load BAS accounts from JSON
    bas_file = os.path.join(os.path.dirname(__file__), "..", "data", "bas_2024.json")
    if not os.path.exists(bas_file):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="BAS 2024 data file not found")

    with open(bas_file, encoding="utf-8") as f:
        bas_data = json.load(f)

    # Create accounts
    created_accounts = []
    for account_data in bas_data["accounts"]:
        account = Account(
            company_id=company_id,
            account_number=account_data["account_number"],
            name=account_data["name"],
            account_type=account_data["account_type"],
            description=account_data.get("description"),
            active=True,
        )
        db.add(account)
        created_accounts.append(account)

    db.commit()

    # Also initialize default account mappings
    default_account_service.initialize_default_accounts_from_existing(db, company_id)

    defaults_count = db.query(DefaultAccount).filter(DefaultAccount.company_id == company_id).count()

    return {
        "message": f"Successfully seeded {len(created_accounts)} BAS 2024 accounts and configured {defaults_count} default account mappings",
        "accounts_created": len(created_accounts),
        "default_accounts_configured": defaults_count,
    }


@router.post("/{company_id}/initialize-defaults", status_code=status.HTTP_200_OK)
def initialize_default_accounts(
    company_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """
    Initialize default account mappings for a company based on existing accounts.
    This is useful after importing SIE4 or when setting up an existing company.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company {company_id} not found")

    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if company_id not in company_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this company")

    # Initialize defaults
    default_account_service.initialize_default_accounts_from_existing(db, company_id)

    # Count configured defaults
    defaults_count = db.query(DefaultAccount).filter(DefaultAccount.company_id == company_id).count()

    return {
        "message": f"Successfully initialized {defaults_count} default account mappings",
        "default_accounts_configured": defaults_count,
    }
