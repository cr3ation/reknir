"""SIE4 Import/Export Router"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.services import sie4_service
from app.dependencies import get_current_active_user, get_user_company_ids
from pydantic import BaseModel

router = APIRouter(prefix="/api/sie4", tags=["SIE4"])


class SIE4ImportResponse(BaseModel):
    """Response model for SIE4 import"""
    success: bool
    message: str
    accounts_created: int
    accounts_updated: int
    verifications_created: int
    default_accounts_configured: int
    errors: list[str] = []
    warnings: list[str] = []


class SIE4ExportRequest(BaseModel):
    """Request model for SIE4 export"""
    company_id: int
    include_verifications: bool = True


@router.post("/import/{company_id}", response_model=SIE4ImportResponse)
async def import_sie4_file(
    company_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Import SIE4 file for a company.

    This will:
    - Import chart of accounts (create new accounts or update existing)
    - Import opening balances
    - Automatically configure default account mappings
    - Optionally import verifications (if included in file)
    """
    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if company_id not in company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this company"
        )

    try:
        # Read file content
        content = await file.read()

        # Try different encodings (SIE files can use various encodings)
        file_content = None
        for encoding in ['cp437', 'iso-8859-1', 'windows-1252', 'utf-8']:
            try:
                file_content = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if file_content is None:
            raise ValueError("Could not decode SIE4 file. Unsupported encoding.")

        # Import
        stats = sie4_service.import_sie4(db, company_id, file_content)

        return SIE4ImportResponse(
            success=True,
            message=f"Successfully imported SIE4 file for company {company_id}",
            **stats
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Import failed: {str(e)}")


@router.get("/export/{company_id}", response_class=PlainTextResponse)
def export_sie4_file(
    company_id: int,
    include_verifications: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Export company data to SIE4 format.

    Returns a SIE4 formatted text file.
    """
    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if company_id not in company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this company"
        )

    try:
        sie4_content = sie4_service.export_sie4(db, company_id, include_verifications)
        return PlainTextResponse(
            content=sie4_content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename=company_{company_id}_{sie4_service.date.today().strftime('%Y%m%d')}.se"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Export failed: {str(e)}")
