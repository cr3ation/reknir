"""
API endpoints for company invitations
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user, verify_company_access
from app.models.company import Company
from app.models.invitation import Invitation
from app.models.user import CompanyUser, User
from app.schemas.invitation import InvitationAccept, InvitationCreate, InvitationResponse, InvitationValidateResponse
from app.services.auth_service import create_user

router = APIRouter(prefix="/api/invitations", tags=["invitations"])


@router.post("/", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    invitation_data: InvitationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create a new company invitation

    Only users with access to the company can create invitations.
    Admins can create invitations for any company.

    Args:
        invitation_data: Invitation creation data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created invitation with token

    Raises:
        HTTPException 403: If user doesn't have access to company
        HTTPException 404: If company not found
    """
    # Verify user has access to this company
    await verify_company_access(invitation_data.company_id, current_user, db)

    # Verify company exists
    company = db.query(Company).filter(Company.id == invitation_data.company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Company {invitation_data.company_id} not found"
        )

    # Create invitation
    invitation = Invitation.create_invitation(
        company_id=invitation_data.company_id,
        created_by_user_id=current_user.id,
        role=invitation_data.role,
        days_valid=invitation_data.days_valid,
    )

    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    return invitation


@router.get("/company/{company_id}", response_model=list[InvitationResponse])
async def list_company_invitations(
    company_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """
    List all invitations for a company

    Only users with access to the company can list invitations.

    Args:
        company_id: Company ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of invitations

    Raises:
        HTTPException 403: If user doesn't have access to company
    """
    # Verify user has access to this company
    await verify_company_access(company_id, current_user, db)

    # Get invitations (most recent first)
    invitations = (
        db.query(Invitation).filter(Invitation.company_id == company_id).order_by(Invitation.created_at.desc()).all()
    )

    return invitations


@router.delete("/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invitation(
    invitation_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """
    Delete/revoke an invitation

    Only users with access to the company can delete invitations.

    Args:
        invitation_id: Invitation ID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException 404: If invitation not found
        HTTPException 403: If user doesn't have access to company
    """
    invitation = db.query(Invitation).filter(Invitation.id == invitation_id).first()
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invitation {invitation_id} not found")

    # Verify user has access to this company
    await verify_company_access(invitation.company_id, current_user, db)

    db.delete(invitation)
    db.commit()


# ==================== Public Endpoints (No Auth Required) ====================


@router.get("/validate/{token}", response_model=InvitationValidateResponse)
def validate_invitation_token(token: str, db: Session = Depends(get_db)):
    """
    Validate an invitation token (PUBLIC endpoint)

    Check if a token is valid and return company information.
    This endpoint does not require authentication.

    Args:
        token: Invitation token
        db: Database session

    Returns:
        Validation result with company info if valid
    """
    invitation = db.query(Invitation).filter(Invitation.token == token).first()

    if not invitation:
        return InvitationValidateResponse(valid=False, message="Invalid invitation link")

    if not invitation.is_valid():
        if invitation.used:
            message = "This invitation has already been used"
        else:
            message = "This invitation has expired"

        return InvitationValidateResponse(valid=False, message=message)

    # Get company name
    company = db.query(Company).filter(Company.id == invitation.company_id).first()

    return InvitationValidateResponse(
        valid=True, company_name=company.name if company else "Unknown", role=invitation.role
    )


@router.post("/accept/{token}", response_model=dict, status_code=status.HTTP_201_CREATED)
def accept_invitation(token: str, user_data: InvitationAccept, db: Session = Depends(get_db)):
    """
    Accept an invitation and create a new user (PUBLIC endpoint)

    This endpoint does not require authentication.
    It creates a new user and automatically assigns them to the company.

    Args:
        token: Invitation token
        user_data: User registration data
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException 400: If invitation invalid or email already exists
    """
    # Find invitation
    invitation = db.query(Invitation).filter(Invitation.token == token).first()
    if not invitation:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invitation link")

    # Check if valid
    if not invitation.is_valid():
        if invitation.used:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has already been used")
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has expired")

    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An account with this email already exists")

    # Create user
    new_user = create_user(
        db=db, email=user_data.email, password=user_data.password, full_name=user_data.full_name, is_admin=False
    )

    # Assign user to company
    company_user = CompanyUser(
        company_id=invitation.company_id,
        user_id=new_user.id,
        role=invitation.role,
        created_by=invitation.created_by_user_id,
    )
    db.add(company_user)

    # Mark invitation as used
    invitation.mark_as_used(new_user.id)

    db.commit()

    return {
        "message": "Account created successfully! You can now log in.",
        "user_id": new_user.id,
        "email": new_user.email,
    }
