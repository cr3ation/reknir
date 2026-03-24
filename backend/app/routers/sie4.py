"""SIE4 Import/Export Router"""

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user, get_user_company_ids
from app.models.user import User
from app.services import sie4_service

router = APIRouter(prefix="/api/sie4", tags=["SIE4"])


class SIE4ImportResponse(BaseModel):
    """Response model for SIE4 import"""

    success: bool
    message: str
    accounts_created: int
    accounts_updated: int
    verifications_created: int
    verifications_skipped: int = 0
    default_accounts_configured: int
    fiscal_year_id: int | None = None
    fiscal_year_created: bool = False
    errors: list[str] = []
    warnings: list[str] = []


class SIE4ExportRequest(BaseModel):
    """Request model for SIE4 export"""

    company_id: int
    include_verifications: bool = True


class SIE4PreviewResponse(BaseModel):
    """Response model for SIE4 preview"""

    can_import: bool
    fiscal_year_start: date | None
    fiscal_year_end: date | None
    fiscal_year_exists: bool
    existing_fiscal_year_id: int | None
    will_create_fiscal_year: bool
    accounts_count: int
    verifications_count: int
    blocking_errors: list[str] = []
    warnings: list[str] = []


@router.post("/preview/{company_id}", response_model=SIE4PreviewResponse)
async def preview_sie4_file(
    company_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Preview SIE4 file import without making changes.

    Analyzes the file and returns:
    - Fiscal year from #RAR 0
    - Whether fiscal year exists or will be created
    - Count of accounts and verifications to import
    - Any blocking errors or warnings

    This is a read-only operation.
    """
    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if company_id not in company_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this company")

    try:
        # Read file content
        content = await file.read()

        # Try different encodings (SIE files can use various encodings)
        file_content = None
        for encoding in ["cp437", "iso-8859-1", "windows-1252", "utf-8"]:
            try:
                file_content = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if file_content is None:
            return SIE4PreviewResponse(
                can_import=False,
                fiscal_year_start=None,
                fiscal_year_end=None,
                fiscal_year_exists=False,
                existing_fiscal_year_id=None,
                will_create_fiscal_year=False,
                accounts_count=0,
                verifications_count=0,
                blocking_errors=["Kunde inte avkoda SIE4-filen. Okänd teckenkodning."],
                warnings=[],
            )

        # Preview
        preview = sie4_service.preview_sie4(db, company_id, file_content)
        return SIE4PreviewResponse(**preview)

    except Exception as e:
        return SIE4PreviewResponse(
            can_import=False,
            fiscal_year_start=None,
            fiscal_year_end=None,
            fiscal_year_exists=False,
            existing_fiscal_year_id=None,
            will_create_fiscal_year=False,
            accounts_count=0,
            verifications_count=0,
            blocking_errors=[f"Förhandsvisning misslyckades: {str(e)}"],
            warnings=[],
        )


@router.post("/import/{company_id}", response_model=SIE4ImportResponse)
async def import_sie4_file(
    company_id: int,
    file: UploadFile = File(...),
    fiscal_year_id: int | None = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Import SIE4 file for a company.

    The fiscal year is determined from the file's #RAR 0 entry. If a matching
    fiscal year exists, it will be used. If not, a new fiscal year will be created.

    Args:
        company_id: Company to import to
        file: SIE4 file (.se or .si)
        fiscal_year_id: Optional fiscal year ID to use (if None, uses #RAR 0 from file)

    This will:
    - Create or use fiscal year from #RAR 0
    - Import chart of accounts (create new accounts or update existing)
    - Import opening balances
    - Automatically configure default account mappings
    - Import verifications (if included in file)
    """
    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if company_id not in company_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this company")

    try:
        # Read file content
        content = await file.read()

        # Try different encodings (SIE files can use various encodings)
        file_content = None
        for encoding in ["cp437", "iso-8859-1", "windows-1252", "utf-8"]:
            try:
                file_content = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if file_content is None:
            raise ValueError("Could not decode SIE4 file. Unsupported encoding.")

        # Import
        stats = sie4_service.import_sie4(db, company_id, file_content, fiscal_year_id)

        return SIE4ImportResponse(
            success=True, message=f"Successfully imported SIE4 file for company {company_id}", **stats
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Import failed: {str(e)}") from e


@router.get("/export/{company_id}", response_class=PlainTextResponse)
def export_sie4_file(
    company_id: int,
    fiscal_year_id: int,
    include_verifications: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Export company data to SIE4 format.

    Returns a SIE4 formatted text file.
    """
    # Verify access
    company_ids = get_user_company_ids(current_user, db)
    if company_id not in company_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this company")

    try:
        sie4_content = sie4_service.export_sie4(db, company_id, fiscal_year_id, include_verifications)
        return PlainTextResponse(
            content=sie4_content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename=company_{company_id}_{sie4_service.date.today().strftime('%Y%m%d')}.se"
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Export failed: {str(e)}") from e
