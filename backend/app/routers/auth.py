"""
Authentication router for login, registration, and user management
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_active_user, get_user_company_ids, require_admin
from app.models.company import Company
from app.models.user import CompanyUser, User
from app.schemas.company import CompanyResponse
from app.schemas.user import (
    ApiKeyExchangeRequest,
    ApiKeyRotateResponse,
    CompanyAccessRequest,
    CompanyUserResponse,
    ServiceAccountCreate,
    ServiceAccountCreated,
    ServiceAccountResponse,
    Token,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.auth_service import (
    authenticate_by_api_key,
    authenticate_user,
    create_access_token,
    create_service_account,
    create_user,
    get_password_hash,
    rotate_api_key,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login endpoint - authenticate user and return JWT token

    Args:
        form_data: OAuth2 form with username (email) and password
        db: Database session

    Returns:
        JWT access token

    Raises:
        HTTPException 401: If credentials are invalid
    """
    user = authenticate_user(db, form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User account is inactive")

    if user.is_service_account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service accounts cannot use password login. Use /api/auth/token/api-key instead.",
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "is_admin": user.is_admin}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/token/api-key", response_model=Token)
def exchange_api_key(request: ApiKeyExchangeRequest, db: Session = Depends(get_db)):
    """Exchange an API key for a JWT token. Used by service accounts."""
    user = authenticate_by_api_key(db, request.api_key)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Service account is inactive")

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "is_admin": user.is_admin,
            "is_service_account": True,
        },
        expires_delta=timedelta(hours=1),
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user (first user only, or by admin later via /api/admin/users)

    This endpoint is only available when no users exist in the system.
    The first user will automatically be an admin.
    After that, only admins can create users via the admin endpoints.

    Args:
        user_data: User creation data
        db: Database session

    Returns:
        Created user

    Raises:
        HTTPException 403: If users already exist in system
        HTTPException 400: If email already exists
    """
    # Check if any users exist
    user_count = db.query(User).count()

    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is closed. Contact an administrator to create an account.",
        )

    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # Create first user as admin
    user = create_user(
        db=db,
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name,
        is_admin=True,  # First user is always admin
    )

    return user


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """
    Get current authenticated user's information

    Args:
        current_user: Current authenticated user

    Returns:
        Current user information
    """
    return current_user


@router.get("/me/companies", response_model=list[CompanyResponse])
async def get_my_companies(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    Get list of companies that the current user has access to

    Admins will get all companies.
    Regular users will get only their assigned companies.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of companies user has access to
    """
    company_ids = get_user_company_ids(current_user, db)
    companies = db.query(Company).filter(Company.id.in_(company_ids)).all()
    return companies


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """
    Update current user's information

    Users can update their own email, full_name, and password.
    Cannot change is_admin or is_active status.

    Args:
        user_update: User update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated user information
    """
    # Check if email is being changed and already exists
    if user_update.email and user_update.email != current_user.email:
        existing = db.query(User).filter(User.email == user_update.email).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use")
        current_user.email = user_update.email

    # Update other fields
    if user_update.full_name:
        current_user.full_name = user_update.full_name

    if user_update.password:
        current_user.hashed_password = get_password_hash(user_update.password)

    db.commit()
    db.refresh(current_user)

    return current_user


# ==================== Admin Endpoints ====================


@router.get("/users", response_model=list[UserResponse])
async def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin: List all users in the system

    Args:
        admin: Current admin user
        db: Database session

    Returns:
        List of all users
    """
    users = db.query(User).filter(User.is_service_account.is_(False)).all()
    return users


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(user_data: UserCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin: Create a new user

    Args:
        user_data: User creation data
        admin: Current admin user
        db: Database session

    Returns:
        Created user

    Raises:
        HTTPException 400: If email already exists
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # Create user (not admin by default)
    user = create_user(
        db=db, email=user_data.email, password=user_data.password, full_name=user_data.full_name, is_admin=False
    )

    return user


@router.post("/users/{user_id}/companies/{company_id}", response_model=CompanyUserResponse)
async def grant_company_access(
    user_id: int,
    company_id: int,
    access_data: CompanyAccessRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin: Grant a user access to a company

    Args:
        user_id: ID of user to grant access
        company_id: ID of company to grant access to
        access_data: Access details (role)
        admin: Current admin user
        db: Database session

    Returns:
        Created company-user association

    Raises:
        HTTPException 404: If user or company not found
        HTTPException 400: If access already exists
    """
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")

    # Verify company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company {company_id} not found")

    # Check if access already exists
    existing = (
        db.query(CompanyUser).filter(CompanyUser.user_id == user_id, CompanyUser.company_id == company_id).first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"User {user_id} already has access to company {company_id}"
        )

    # Create access
    company_user = CompanyUser(company_id=company_id, user_id=user_id, role=access_data.role, created_by=admin.id)

    db.add(company_user)
    db.commit()
    db.refresh(company_user)

    return company_user


@router.delete("/users/{user_id}/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_company_access(
    user_id: int, company_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    """
    Admin: Revoke a user's access to a company

    Args:
        user_id: ID of user
        company_id: ID of company
        admin: Current admin user
        db: Database session

    Raises:
        HTTPException 404: If access record not found
    """
    company_user = (
        db.query(CompanyUser).filter(CompanyUser.user_id == user_id, CompanyUser.company_id == company_id).first()
    )

    if not company_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} doesn't have access to company {company_id}"
        )

    db.delete(company_user)
    db.commit()


@router.get("/users/{user_id}/companies", response_model=list[CompanyResponse])
async def get_user_companies(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin: Get list of companies a user has access to

    Args:
        user_id: ID of user
        admin: Current admin user
        db: Database session

    Returns:
        List of companies

    Raises:
        HTTPException 404: If user not found
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")

    company_ids = get_user_company_ids(user, db)
    companies = db.query(Company).filter(Company.id.in_(company_ids)).all()
    return companies


# ==================== Service Account Endpoints ====================


@router.post("/service-accounts", response_model=ServiceAccountCreated, status_code=status.HTTP_201_CREATED)
async def create_service_account_endpoint(
    data: ServiceAccountCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    """Admin: Create a service account. The API key is returned once — store it securely."""
    user, api_key = create_service_account(db, full_name=data.full_name, owner_id=admin.id)
    return ServiceAccountCreated(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        is_admin=user.is_admin,
        is_active=user.is_active,
        is_service_account=user.is_service_account,
        owner_id=user.owner_id,
        created_at=user.created_at,
        api_key=api_key,
    )


@router.get("/service-accounts", response_model=list[ServiceAccountResponse])
async def list_service_accounts(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Admin: List all service accounts."""
    return db.query(User).filter(User.is_service_account.is_(True)).all()


@router.delete("/service-accounts/{service_account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_service_account(
    service_account_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    """Admin: Deactivate a service account."""
    sa = db.query(User).filter(User.id == service_account_id, User.is_service_account.is_(True)).first()
    if not sa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service account not found")
    sa.is_active = False
    db.commit()


@router.post("/service-accounts/{service_account_id}/rotate-key", response_model=ApiKeyRotateResponse)
async def rotate_service_account_key(
    service_account_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    """Admin: Rotate the API key for a service account. Returns the new key once."""
    sa = db.query(User).filter(User.id == service_account_id, User.is_service_account.is_(True)).first()
    if not sa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service account not found")
    new_key = rotate_api_key(db, sa)
    return {"api_key": new_key}
