from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from app.database import get_db
from app.models.fiscal_year import FiscalYear
from app.models.company import Company
from app.models.verification import Verification
from app.models.user import User
from app.schemas.fiscal_year import FiscalYearCreate, FiscalYearResponse, FiscalYearUpdate
from app.dependencies import get_current_active_user, verify_company_access, get_user_company_ids

router = APIRouter()


@router.post("/", response_model=FiscalYearResponse, status_code=status.HTTP_201_CREATED)
def create_fiscal_year(
    fiscal_year: FiscalYearCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new fiscal year"""
    # Verify user has access to this company
    company_ids = get_user_company_ids(current_user, db)
    if fiscal_year.company_id not in company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You don't have access to company {fiscal_year.company_id}"
        )

    # Verify company exists
    company = db.query(Company).filter(Company.id == fiscal_year.company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {fiscal_year.company_id} not found"
        )

    # Check for overlapping fiscal years
    overlapping = db.query(FiscalYear).filter(
        FiscalYear.company_id == fiscal_year.company_id,
        FiscalYear.start_date <= fiscal_year.end_date,
        FiscalYear.end_date >= fiscal_year.start_date
    ).first()

    if overlapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fiscal year overlaps with existing fiscal year {overlapping.label}"
        )

    # Create fiscal year
    db_fiscal_year = FiscalYear(**fiscal_year.model_dump())
    db.add(db_fiscal_year)
    db.commit()
    db.refresh(db_fiscal_year)

    return db_fiscal_year


@router.get("/", response_model=List[FiscalYearResponse])
def list_fiscal_years(
    company_id: int = Query(..., description="Company ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    _: None = Depends(verify_company_access)
):
    """List all fiscal years for a company"""
    fiscal_years = db.query(FiscalYear).filter(
        FiscalYear.company_id == company_id
    ).order_by(FiscalYear.year.desc()).all()

    return fiscal_years


@router.get("/{fiscal_year_id}", response_model=FiscalYearResponse)
def get_fiscal_year(
    fiscal_year_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific fiscal year"""
    fiscal_year = db.query(FiscalYear).filter(FiscalYear.id == fiscal_year_id).first()
    if not fiscal_year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fiscal year {fiscal_year_id} not found"
        )

    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if fiscal_year.company_id not in company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this fiscal year"
        )

    return fiscal_year


@router.get("/current/by-company/{company_id}", response_model=Optional[FiscalYearResponse])
def get_current_fiscal_year(
    company_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get the current fiscal year for a company (based on today's date)"""
    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if company_id not in company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this company"
        )

    today = date.today()

    fiscal_year = db.query(FiscalYear).filter(
        FiscalYear.company_id == company_id,
        FiscalYear.start_date <= today,
        FiscalYear.end_date >= today
    ).first()

    return fiscal_year


@router.patch("/{fiscal_year_id}", response_model=FiscalYearResponse)
def update_fiscal_year(
    fiscal_year_id: int,
    fiscal_year_update: FiscalYearUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a fiscal year"""
    fiscal_year = db.query(FiscalYear).filter(FiscalYear.id == fiscal_year_id).first()
    if not fiscal_year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fiscal year {fiscal_year_id} not found"
        )

    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if fiscal_year.company_id not in company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this fiscal year"
        )

    # Update fields
    update_data = fiscal_year_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(fiscal_year, field, value)

    db.commit()
    db.refresh(fiscal_year)
    return fiscal_year


@router.delete("/{fiscal_year_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fiscal_year(
    fiscal_year_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a fiscal year (WARNING: will detach all associated verifications)"""
    fiscal_year = db.query(FiscalYear).filter(FiscalYear.id == fiscal_year_id).first()
    if not fiscal_year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fiscal year {fiscal_year_id} not found"
        )

    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if fiscal_year.company_id not in company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this fiscal year"
        )

    # Detach verifications (set fiscal_year_id to NULL)
    db.query(Verification).filter(
        Verification.fiscal_year_id == fiscal_year_id
    ).update({"fiscal_year_id": None})

    db.delete(fiscal_year)
    db.commit()
    return None


@router.post("/{fiscal_year_id}/assign-verifications", status_code=status.HTTP_200_OK)
def assign_verifications_to_fiscal_year(
    fiscal_year_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Assign all unassigned verifications to this fiscal year based on transaction_date.
    Also reassign verifications that fall within this fiscal year's date range.
    """
    fiscal_year = db.query(FiscalYear).filter(FiscalYear.id == fiscal_year_id).first()
    if not fiscal_year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fiscal year {fiscal_year_id} not found"
        )

    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if fiscal_year.company_id not in company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this fiscal year"
        )

    # Find verifications within this fiscal year's date range
    verifications = db.query(Verification).filter(
        Verification.company_id == fiscal_year.company_id,
        Verification.transaction_date >= fiscal_year.start_date,
        Verification.transaction_date <= fiscal_year.end_date
    ).all()

    count = 0
    for verification in verifications:
        verification.fiscal_year_id = fiscal_year_id
        count += 1

    db.commit()

    return {
        "message": f"Assigned {count} verifications to fiscal year {fiscal_year.label}",
        "verifications_assigned": count
    }
