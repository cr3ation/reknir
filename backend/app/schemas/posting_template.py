from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import re


class PostingTemplateLineBase(BaseModel):
    """Base verification template line schema"""
    account_id: int = Field(..., description="Account ID for this posting line")
    formula: str = Field(..., description="Formula for calculating the amount (e.g., '{belopp} * 0.25')")
    description: Optional[str] = Field(None, max_length=255, description="Optional line description")
    sort_order: int = Field(0, description="Sort order for line ordering")

    @field_validator('formula')
    @classmethod
    def validate_formula(cls, v):
        """Validate that the formula is syntactically correct and contains {belopp}"""
        if not v or not v.strip():
            raise ValueError("Formula cannot be empty")
        
        if "{belopp}" not in v:
            raise ValueError("Formula must contain the {belopp} variable")
        
        # Test with a dummy value to check syntax
        try:
            test_expression = v.replace("{belopp}", "100")
            # Only allow safe mathematical characters
            if not re.match(r'^[0-9+\-*/.() ]+$', test_expression):
                raise ValueError("Formula contains invalid characters")
            eval(test_expression)
        except Exception as e:
            raise ValueError(f"Invalid formula syntax: {str(e)}")
        
        return v


class PostingTemplateLineCreate(PostingTemplateLineBase):
    """Schema for creating a verification template line"""
    pass


class PostingTemplateLineUpdate(BaseModel):
    """Schema for updating a verification template line"""
    account_id: Optional[int] = None
    formula: Optional[str] = None
    description: Optional[str] = Field(None, max_length=255)
    sort_order: Optional[int] = None

    @field_validator('formula')
    @classmethod
    def validate_formula(cls, v):
        """Validate formula if provided"""
        if v is not None:
            return PostingTemplateLineBase.validate_formula(v)
        return v


class PostingTemplateLineResponse(PostingTemplateLineBase):
    """Schema for verification template line response"""
    id: int
    template_id: int
    
    model_config = {"from_attributes": True}


class PostingTemplateBase(BaseModel):
    """Base verification template schema"""
    name: str = Field(..., max_length=100, description="Template name (e.g., 'Inköp med 25% moms', 'Löner')")
    description: str = Field(..., max_length=255, description="Template description")
    default_series: Optional[str] = Field(None, max_length=10, description="Default verification series")
    default_journal_text: Optional[str] = Field(None, description="Default journal text for verifications")
    sort_order: int = Field(999, description="User-defined sort order for templates")




class PostingTemplateCreate(PostingTemplateBase):
    """Schema for creating a verification template"""
    company_id: int = Field(..., description="Company ID")
    template_lines: List[PostingTemplateLineCreate] = Field(..., description="Template posting lines")

    @field_validator('template_lines')
    @classmethod
    def validate_template_lines(cls, v):
        """Validate that at least one template line is provided"""
        if not v or len(v) == 0:
            raise ValueError("At least one template line is required")
        return v


class PostingTemplateUpdate(BaseModel):
    """Schema for updating a verification template"""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    default_series: Optional[str] = Field(None, max_length=10)
    default_journal_text: Optional[str] = None
    template_lines: Optional[List[PostingTemplateLineCreate]] = None




class PostingTemplateResponse(PostingTemplateBase):
    """Schema for verification template response"""
    id: int
    company_id: int
    created_at: datetime
    updated_at: datetime
    template_lines: List[PostingTemplateLineResponse] = []
    
    model_config = {"from_attributes": True}


class PostingTemplateListItem(BaseModel):
    """Schema for verification template list items (without template lines)"""
    id: int
    name: str
    description: str
    default_series: Optional[str]
    created_at: datetime
    updated_at: datetime
    line_count: int = Field(..., description="Number of posting lines in the template")
    
    model_config = {"from_attributes": True}


# Schemas for template execution
class TemplateExecutionRequest(BaseModel):
    """Schema for executing a verification template"""
    amount: Decimal = Field(..., gt=0, description="Total amount to use in formulas")
    transaction_date: Optional[str] = Field(None, description="Override transaction date (YYYY-MM-DD)")
    description_override: Optional[str] = Field(None, description="Override the default journal text")


class TemplateExecutionLine(BaseModel):
    """Schema for a line in the template execution result"""
    account_id: int
    debit: Decimal
    credit: Decimal
    description: Optional[str]


class TemplateExecutionResult(BaseModel):
    """Schema for template execution result"""
    template_id: int
    template_name: str
    amount: Decimal
    posting_lines: List[TemplateExecutionLine]
    total_debit: Decimal = Field(..., description="Sum of all debit amounts")
    total_credit: Decimal = Field(..., description="Sum of all credit amounts")
    is_balanced: bool = Field(..., description="Whether debit equals credit")
    
    @field_validator('posting_lines')
    @classmethod
    def validate_balance(cls, v, info):
        """Calculate totals and check balance"""
        if 'total_debit' not in info.data or 'total_credit' not in info.data:
            total_debit = sum(line.debit for line in v)
            total_credit = sum(line.credit for line in v)
            info.data['total_debit'] = total_debit
            info.data['total_credit'] = total_credit
            info.data['is_balanced'] = abs(total_debit - total_credit) < Decimal('0.01')
        return v