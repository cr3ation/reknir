"""
Dependency functions for authentication, authorization and request guards
"""

from datetime import date

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.fiscal_year import FiscalYear
from app.models.user import CompanyUser, User
from app.services.auth_service import decode_access_token

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Dependency to get the current authenticated user from JWT token

    Args:
        token: JWT token from Authorization header
        db: Database session

    Returns:
        Current User object

    Raises:
        HTTPException 401: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Decode token
    token_data = decode_access_token(token)
    if token_data is None:
        raise credentials_exception

    # Get user from database
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to ensure the current user is active

    Args:
        current_user: Current user from get_current_user

    Returns:
        Current active User object

    Raises:
        HTTPException 400: If user account is inactive
    """
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user account")
    return current_user


async def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Dependency to require admin privileges

    Args:
        current_user: Current active user

    Returns:
        Current user if admin

    Raises:
        HTTPException 403: If user is not an admin
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user


async def verify_company_access(
    company_id: int = Query(..., description="Company ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Dependency to verify that the current user has access to a specific company

    Admins have access to all companies.
    Regular users must have explicit company access via CompanyUser.

    Args:
        company_id: ID of the company to check access for
        current_user: Current active user
        db: Database session

    Raises:
        HTTPException 403: If user doesn't have access to the company
    """
    # Admins can access all companies
    if current_user.is_admin:
        return

    # Check if user has explicit access to this company
    access = (
        db.query(CompanyUser)
        .filter(CompanyUser.user_id == current_user.id, CompanyUser.company_id == company_id)
        .first()
    )

    if not access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"You don't have access to company {company_id}"
        )


CLOSED_FISCAL_YEAR_DETAIL = "Fiscal year {label} is closed. Post a correcting entry in the current fiscal year instead."


def ensure_fiscal_year_open(db: Session, fiscal_year_id: int) -> FiscalYear:
    """
    Reject a write that would land in a closed fiscal year.

    Swedish bookkeeping law (Bokföringslagen) requires a closed period to stay unchanged,
    so every ledger-affecting path must refuse once the year-end closing has locked it.

    Args:
        db: Database session
        fiscal_year_id: ID of the fiscal year the write targets

    Returns:
        The fiscal year, so callers can reuse it without a second query

    Raises:
        HTTPException 404: If the fiscal year does not exist
        HTTPException 403: If the fiscal year is closed
    """
    fiscal_year = db.query(FiscalYear).filter(FiscalYear.id == fiscal_year_id).first()
    if not fiscal_year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Fiscal year {fiscal_year_id} not found")

    if fiscal_year.is_closed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=CLOSED_FISCAL_YEAR_DETAIL.format(label=fiscal_year.label),
        )

    return fiscal_year


def ensure_fiscal_year_open_for_date(db: Session, company_id: int, transaction_date: date) -> FiscalYear | None:
    """
    Reject a write whose transaction date falls inside a closed fiscal year.

    Used by the paths that derive their fiscal year from a date rather than an explicit id
    (invoices, supplier invoices and expenses). A missing fiscal year is not an error here —
    the posting services raise their own ValueError for that case.

    Args:
        db: Database session
        company_id: Company the write belongs to
        transaction_date: Date the resulting verification will carry

    Returns:
        The matching fiscal year, or None when the date falls outside every fiscal year

    Raises:
        HTTPException 403: If the matching fiscal year is closed
    """
    fiscal_year = (
        db.query(FiscalYear)
        .filter(
            FiscalYear.company_id == company_id,
            FiscalYear.start_date <= transaction_date,
            FiscalYear.end_date >= transaction_date,
        )
        .first()
    )

    if fiscal_year and fiscal_year.is_closed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=CLOSED_FISCAL_YEAR_DETAIL.format(label=fiscal_year.label),
        )

    return fiscal_year


def get_user_company_ids(user: User, db: Session) -> list[int]:
    """
    Get list of company IDs that a user has access to

    Admins get all company IDs.
    Regular users get only their assigned companies.

    Args:
        user: User object
        db: Database session

    Returns:
        List of company IDs
    """
    if user.is_admin:
        # Admin has access to all companies
        from app.models.company import Company

        companies = db.query(Company).all()
        return [c.id for c in companies]
    else:
        # Regular user - get assigned companies
        company_users = db.query(CompanyUser).filter(CompanyUser.user_id == user.id).all()
        return [cu.company_id for cu in company_users]
