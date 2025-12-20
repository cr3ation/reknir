from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_active_user, verify_company_access
from app.models.account import Account
from app.models.company import Company
from app.models.posting_template import PostingTemplate, PostingTemplateLine
from app.models.user import User
from app.schemas.posting_template import (
    PostingTemplateCreate,
    PostingTemplateResponse,
    PostingTemplateUpdate,
    TemplateExecutionLine,
    TemplateExecutionRequest,
    TemplateExecutionResult,
)

router = APIRouter()


@router.post("/", response_model=PostingTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_posting_template(
    template: PostingTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new posting template"""
    # Verify user has access to this company
    await verify_company_access(template.company_id, current_user, db)

    # Verify company exists
    company = db.query(Company).filter(Company.id == template.company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Company with id {template.company_id} not found"
        )

    # Check if template name already exists for this company
    existing = (
        db.query(PostingTemplate)
        .filter(PostingTemplate.company_id == template.company_id, PostingTemplate.name == template.name)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template with name '{template.name}' already exists for this company",
        )

    # Verify all accounts exist
    account_ids = [line.account_id for line in template.template_lines]
    accounts = db.query(Account).filter(Account.id.in_(account_ids), Account.company_id == template.company_id).all()

    if len(accounts) != len(account_ids):
        found_ids = {acc.id for acc in accounts}
        missing_ids = set(account_ids) - found_ids
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Accounts not found: {list(missing_ids)}")

    # Create the posting template
    db_template = PostingTemplate(
        company_id=template.company_id,
        name=template.name,
        description=template.description,
        default_series=template.default_series,
        default_journal_text=template.default_journal_text,
    )
    db.add(db_template)
    db.flush()  # Get template ID

    # Create template lines
    for i, line in enumerate(template.template_lines):
        db_line = PostingTemplateLine(
            template_id=db_template.id,
            account_id=line.account_id,
            formula=line.formula,
            description=line.description,
            sort_order=line.sort_order if line.sort_order > 0 else i,
        )
        db.add(db_line)

    db.commit()
    db.refresh(db_template)

    return db_template


@router.get("/", response_model=list[PostingTemplateResponse])
async def list_posting_templates(
    company_id: int = Query(..., description="Company ID"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all posting templates for a company"""
    # Verify user has access to this company
    await verify_company_access(company_id, current_user, db)

    # Verify company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company with id {company_id} not found")

    # Query templates
    templates = (
        db.query(PostingTemplate)
        .options(joinedload(PostingTemplate.template_lines).joinedload(PostingTemplateLine.account))
        .filter(PostingTemplate.company_id == company_id)
        .order_by(PostingTemplate.sort_order, PostingTemplate.name)
        .offset(skip)
        .limit(limit)
        .all()
    )

    # Sort template lines by sort_order for each template
    for template in templates:
        template.template_lines.sort(key=lambda x: x.sort_order)

    return templates


@router.get("/{template_id}", response_model=PostingTemplateResponse)
async def get_posting_template(
    template_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Get a specific posting template with all its lines"""

    template = (
        db.query(PostingTemplate)
        .options(joinedload(PostingTemplate.template_lines).joinedload(PostingTemplateLine.account))
        .filter(PostingTemplate.id == template_id)
        .first()
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Posting template with id {template_id} not found"
        )

    # Verify user has access to this company
    await verify_company_access(template.company_id, current_user, db)

    # Sort template lines by sort_order
    template.template_lines.sort(key=lambda x: x.sort_order)

    return template


@router.put("/{template_id}", response_model=PostingTemplateResponse)
async def update_posting_template(
    template_id: int,
    template_update: PostingTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a posting template"""

    # Get existing template
    db_template = db.query(PostingTemplate).filter(PostingTemplate.id == template_id).first()

    if not db_template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Posting template with id {template_id} not found"
        )

    # Verify user has access to this company
    await verify_company_access(db_template.company_id, current_user, db)

    # Check for name conflicts if name is being updated
    if template_update.name and template_update.name != db_template.name:
        existing = (
            db.query(PostingTemplate)
            .filter(
                PostingTemplate.company_id == db_template.company_id,
                PostingTemplate.name == template_update.name,
                PostingTemplate.id != template_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Template with name '{template_update.name}' already exists for this company",
            )

    # Update template fields
    if template_update.name is not None:
        db_template.name = template_update.name
    if template_update.description is not None:
        db_template.description = template_update.description
    if template_update.default_series is not None:
        db_template.default_series = template_update.default_series
    if template_update.default_journal_text is not None:
        db_template.default_journal_text = template_update.default_journal_text

    # Update template lines if provided
    if template_update.template_lines is not None:
        # Delete existing lines
        db.query(PostingTemplateLine).filter(PostingTemplateLine.template_id == template_id).delete()

        # Verify all accounts exist
        account_ids = [line.account_id for line in template_update.template_lines]
        accounts = (
            db.query(Account).filter(Account.id.in_(account_ids), Account.company_id == db_template.company_id).all()
        )

        if len(accounts) != len(account_ids):
            found_ids = {acc.id for acc in accounts}
            missing_ids = set(account_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Accounts not found: {list(missing_ids)}"
            )

        # Create new lines
        for i, line in enumerate(template_update.template_lines):
            db_line = PostingTemplateLine(
                template_id=template_id,
                account_id=line.account_id,
                formula=line.formula,
                description=line.description,
                sort_order=line.sort_order if line.sort_order > 0 else i,
            )
            db.add(db_line)

    db.commit()
    db.refresh(db_template)

    return db_template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_posting_template(
    template_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
):
    """Delete a posting template"""

    template = db.query(PostingTemplate).filter(PostingTemplate.id == template_id).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Posting template with id {template_id} not found"
        )

    # Verify user has access to this company
    await verify_company_access(template.company_id, current_user, db)

    # Delete template (cascade will handle lines)
    db.delete(template)
    db.commit()

    return None


@router.post("/{template_id}/execute", response_model=TemplateExecutionResult)
async def execute_posting_template(
    template_id: int,
    execution_request: TemplateExecutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Execute a posting template with a given amount for a specific fiscal year.
    Returns the calculated posting lines without creating a verification.

    The template will automatically translate account references to the target fiscal year.
    """
    from app.models.fiscal_year import FiscalYear

    # Get template with lines and account relationships
    template = (
        db.query(PostingTemplate)
        .options(joinedload(PostingTemplate.template_lines).joinedload(PostingTemplateLine.account))
        .filter(PostingTemplate.id == template_id)
        .first()
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Posting template with id {template_id} not found"
        )

    # Verify user has access to this company
    await verify_company_access(template.company_id, current_user, db)

    if not template.template_lines:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template has no posting lines")

    # Verify fiscal year exists and belongs to the same company
    fiscal_year = db.query(FiscalYear).filter(FiscalYear.id == execution_request.fiscal_year_id).first()

    if not fiscal_year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fiscal year with id {execution_request.fiscal_year_id} not found",
        )

    if fiscal_year.company_id != template.company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fiscal year does not belong to the same company as the template",
        )

    try:
        # Execute the template to get posting lines for the target fiscal year
        posting_lines_data = template.evaluate_template(
            db, float(execution_request.amount), execution_request.fiscal_year_id
        )

        # Convert to response format
        posting_lines = []
        total_debit = Decimal("0")
        total_credit = Decimal("0")

        for line_data in posting_lines_data:
            debit = Decimal(str(line_data["debit"]))
            credit = Decimal(str(line_data["credit"]))

            posting_line = TemplateExecutionLine(
                account_id=line_data["account_id"], debit=debit, credit=credit, description=line_data["description"]
            )
            posting_lines.append(posting_line)

            total_debit += debit
            total_credit += credit

        # Check balance
        is_balanced = abs(total_debit - total_credit) < Decimal("0.01")

        return TemplateExecutionResult(
            template_id=template_id,
            template_name=template.name,
            amount=execution_request.amount,
            posting_lines=posting_lines,
            total_debit=total_debit,
            total_credit=total_credit,
            is_balanced=is_balanced,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error executing template: {str(e)}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error executing template: {str(e)}"
        ) from e


@router.patch("/reorder", status_code=status.HTTP_200_OK)
async def reorder_posting_templates(
    template_orders: list[dict],
    company_id: int = Query(..., description="Company ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update sort order for posting templates

    Expected format: [{"id": 1, "sort_order": 1}, {"id": 2, "sort_order": 2}, ...]
    """
    # Verify user has access to this company
    await verify_company_access(company_id, current_user, db)

    # Verify company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company with id {company_id} not found")

    try:
        # Update each template's sort order
        for item in template_orders:
            template_id = item.get("id")
            sort_order = item.get("sort_order")

            if template_id is None or sort_order is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Each item must have 'id' and 'sort_order' fields"
                )

            # Update the template if it belongs to this company
            template = (
                db.query(PostingTemplate)
                .filter(PostingTemplate.id == template_id, PostingTemplate.company_id == company_id)
                .first()
            )

            if template:
                template.sort_order = sort_order

        db.commit()

        return {
            "message": f"Successfully updated sort order for {len(template_orders)} templates",
            "templates_updated": len(template_orders),
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update template order: {str(e)}"
        ) from e
