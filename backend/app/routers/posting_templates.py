from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func
from typing import List, Optional
from datetime import date
from decimal import Decimal
from app.database import get_db
from app.models.posting_template import PostingTemplate, PostingTemplateLine
from app.models.account import Account
from app.models.company import Company
from app.schemas.posting_template import (
    PostingTemplateCreate,
    PostingTemplateUpdate,
    PostingTemplateResponse,
    PostingTemplateListItem,
    TemplateExecutionRequest,
    TemplateExecutionResult,
    TemplateExecutionLine
)

router = APIRouter()


@router.post("/", response_model=PostingTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_posting_template(
    template: PostingTemplateCreate, 
    db: Session = Depends(get_db)
):
    """Create a new posting template"""
    
    # Verify company exists
    company = db.query(Company).filter(Company.id == template.company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with id {template.company_id} not found"
        )
    
    # Check if template name already exists for this company
    existing = db.query(PostingTemplate).filter(
        PostingTemplate.company_id == template.company_id,
        PostingTemplate.name == template.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template with name '{template.name}' already exists for this company"
        )
    
    # Verify all accounts exist
    account_ids = [line.account_id for line in template.template_lines]
    accounts = db.query(Account).filter(
        Account.id.in_(account_ids),
        Account.company_id == template.company_id
    ).all()
    
    if len(accounts) != len(account_ids):
        found_ids = {acc.id for acc in accounts}
        missing_ids = set(account_ids) - found_ids
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Accounts not found: {list(missing_ids)}"
        )
    
    # Create the posting template
    db_template = PostingTemplate(
        company_id=template.company_id,
        name=template.name,
        description=template.description,
        default_series=template.default_series,
        default_journal_text=template.default_journal_text
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
            sort_order=line.sort_order if line.sort_order > 0 else i
        )
        db.add(db_line)
    
    db.commit()
    db.refresh(db_template)
    
    return db_template


@router.get("/", response_model=List[PostingTemplateListItem])
def list_posting_templates(
    company_id: int = Query(..., description="Company ID"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db)
):
    """List all posting templates for a company"""
    
    # Verify company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with id {company_id} not found"
        )
    
    # Query templates with line count
    templates = db.query(
        PostingTemplate,
        func.count(PostingTemplateLine.id).label('line_count')
    ).outerjoin(
        PostingTemplateLine,
        PostingTemplate.id == PostingTemplateLine.template_id
    ).filter(
        PostingTemplate.company_id == company_id
    ).group_by(
        PostingTemplate.id
    ).order_by(
        PostingTemplate.name
    ).offset(skip).limit(limit).all()
    
    # Convert to list items
    result = []
    for template, line_count in templates:
        item = PostingTemplateListItem(
            id=template.id,
            name=template.name,
            description=template.description,
            default_series=template.default_series,
            created_at=template.created_at,
            updated_at=template.updated_at,
            line_count=line_count or 0
        )
        result.append(item)
    
    return result


@router.get("/{template_id}", response_model=PostingTemplateResponse)
def get_posting_template(template_id: int, db: Session = Depends(get_db)):
    """Get a specific posting template with all its lines"""
    
    template = db.query(PostingTemplate).options(
        joinedload(PostingTemplate.template_lines).joinedload(PostingTemplateLine.account)
    ).filter(PostingTemplate.id == template_id).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Posting template with id {template_id} not found"
        )
    
    # Sort template lines by sort_order
    template.template_lines.sort(key=lambda x: x.sort_order)
    
    return template


@router.put("/{template_id}", response_model=PostingTemplateResponse)
def update_posting_template(
    template_id: int,
    template_update: PostingTemplateUpdate,
    db: Session = Depends(get_db)
):
    """Update a posting template"""
    
    # Get existing template
    db_template = db.query(PostingTemplate).filter(
        PostingTemplate.id == template_id
    ).first()
    
    if not db_template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Posting template with id {template_id} not found"
        )
    
    # Check for name conflicts if name is being updated
    if template_update.name and template_update.name != db_template.name:
        existing = db.query(PostingTemplate).filter(
            PostingTemplate.company_id == db_template.company_id,
            PostingTemplate.name == template_update.name,
            PostingTemplate.id != template_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Template with name '{template_update.name}' already exists for this company"
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
        db.query(PostingTemplateLine).filter(
            PostingTemplateLine.template_id == template_id
        ).delete()
        
        # Verify all accounts exist
        account_ids = [line.account_id for line in template_update.template_lines]
        accounts = db.query(Account).filter(
            Account.id.in_(account_ids),
            Account.company_id == db_template.company_id
        ).all()
        
        if len(accounts) != len(account_ids):
            found_ids = {acc.id for acc in accounts}
            missing_ids = set(account_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Accounts not found: {list(missing_ids)}"
            )
        
        # Create new lines
        for i, line in enumerate(template_update.template_lines):
            db_line = PostingTemplateLine(
                template_id=template_id,
                account_id=line.account_id,
                formula=line.formula,
                description=line.description,
                sort_order=line.sort_order if line.sort_order > 0 else i
            )
            db.add(db_line)
    
    db.commit()
    db.refresh(db_template)
    
    return db_template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_posting_template(template_id: int, db: Session = Depends(get_db)):
    """Delete a posting template"""
    
    template = db.query(PostingTemplate).filter(
        PostingTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Posting template with id {template_id} not found"
        )
    
    # Delete template (cascade will handle lines)
    db.delete(template)
    db.commit()
    
    return None


@router.post("/{template_id}/execute", response_model=TemplateExecutionResult)
def execute_posting_template(
    template_id: int,
    execution_request: TemplateExecutionRequest,
    db: Session = Depends(get_db)
):
    """
    Execute a posting template with a given amount
    Returns the calculated posting lines without creating a verification
    """
    
    # Get template with lines
    template = db.query(PostingTemplate).options(
        joinedload(PostingTemplate.template_lines)
    ).filter(PostingTemplate.id == template_id).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Posting template with id {template_id} not found"
        )
    
    if not template.template_lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template has no posting lines"
        )
    
    try:
        # Execute the template to get posting lines
        posting_lines_data = template.evaluate_template(float(execution_request.amount))
        
        # Convert to response format
        posting_lines = []
        total_debit = Decimal('0')
        total_credit = Decimal('0')
        
        for line_data in posting_lines_data:
            debit = Decimal(str(line_data['debit']))
            credit = Decimal(str(line_data['credit']))
            
            posting_line = TemplateExecutionLine(
                account_id=line_data['account_id'],
                debit=debit,
                credit=credit,
                description=line_data['description']
            )
            posting_lines.append(posting_line)
            
            total_debit += debit
            total_credit += credit
        
        # Check balance
        is_balanced = abs(total_debit - total_credit) < Decimal('0.01')
        
        return TemplateExecutionResult(
            template_id=template_id,
            template_name=template.name,
            amount=execution_request.amount,
            posting_lines=posting_lines,
            total_debit=total_debit,
            total_credit=total_credit,
            is_balanced=is_balanced
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error executing template: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error executing template: {str(e)}"
        )