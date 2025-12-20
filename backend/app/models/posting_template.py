import re

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class PostingTemplate(Base):
    """
    Posting Template (Bokföringsmall)
    A template for creating recurring journal entries with predefined posting logic
    """

    __tablename__ = "posting_templates"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    # Template metadata
    name = Column(String(100), nullable=False, index=True)  # Template name (e.g., "Inköp med 25% moms", "Löner")
    description = Column(String(255), nullable=False)  # Template description
    default_series = Column(String(10), nullable=True)  # Optional default series (A, B, C, etc.)
    default_journal_text = Column(Text, nullable=True)  # Optional default verification text
    sort_order = Column(Integer, nullable=False, default=999)  # User-defined sort order for templates

    # Audit trail
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    company = relationship("Company", back_populates="posting_templates")
    template_lines = relationship("PostingTemplateLine", back_populates="template", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PostingTemplate {self.name} - {self.description}>"

    def evaluate_template(self, db, amount: float, fiscal_year_id: int) -> list:
        """
        Evaluate the template with a given amount and return posting lines for a specific fiscal year.

        Args:
            db: Database session
            amount: The amount to use in formula calculations
            fiscal_year_id: The target fiscal year to find accounts in

        Returns:
            List of dicts with account_id, debit, credit, description, etc.

        The method translates account references from the template's original fiscal year
        to equivalent accounts (same account_number) in the target fiscal year.
        """
        from app.models.account import Account

        posting_lines = []

        for line in self.template_lines:
            # Get the template's account to find its account_number
            template_account = line.account

            # Find the equivalent account in the target fiscal year
            target_account = (
                db.query(Account)
                .filter(
                    Account.company_id == self.company_id,
                    Account.fiscal_year_id == fiscal_year_id,
                    Account.account_number == template_account.account_number,
                )
                .first()
            )

            if not target_account:
                raise ValueError(
                    f"Account {template_account.account_number} ({template_account.name}) "
                    f"not found in fiscal year {fiscal_year_id}. "
                    f"Please ensure the account exists in the target fiscal year."
                )

            evaluated_amount = line.evaluate_formula(amount)

            # Positive amounts become debits, negative become credits
            debit = max(0, evaluated_amount)
            credit = abs(min(0, evaluated_amount))

            posting_line = {
                "account_id": target_account.id,
                "debit": debit,
                "credit": credit,
                "description": line.description,
            }
            posting_lines.append(posting_line)

        return posting_lines


class PostingTemplateLine(Base):
    """
    Individual posting line in a posting template
    Contains account reference and a formula for amount calculation.

    The account_id references a specific account in a specific fiscal year.
    When using templates across fiscal years, the system will find the equivalent
    account (same account_number) in the target fiscal year.
    """

    __tablename__ = "posting_template_lines"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("posting_templates.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)

    # Formula for amount calculation
    formula = Column(String(500), nullable=False)  # e.g., "{total} * 0.25", "-{total}"

    # Optional line description (overrides template description)
    description = Column(String(255), nullable=True)

    # Sort order for consistent line ordering
    sort_order = Column(Integer, default=0, nullable=False)

    # Relationships
    template = relationship("PostingTemplate", back_populates="template_lines")
    account = relationship("Account")

    def __repr__(self):
        return f"<PostingTemplateLine Account:{self.account_id} Formula:{self.formula}>"

    def evaluate_formula(self, amount: float) -> float:
        """
        Evaluate the formula with the given amount
        Replaces {total} variable and calculates the result
        """
        try:
            # Replace the {total} variable with the actual value
            expression = self.formula.replace("{total}", str(amount))

            # Validate the expression contains only allowed characters
            if not re.match(r"^[0-9+\-*/.() ]+$", expression):
                raise ValueError(f"Invalid formula: {self.formula}")

            # Evaluate the mathematical expression
            # Note: In production, consider using a safer eval alternative like simpleeval
            result = eval(expression)

            return float(result)

        except Exception as e:
            raise ValueError(f"Error evaluating formula '{self.formula}' with amount {amount}: {str(e)}") from e

    @staticmethod
    def validate_formula(formula: str) -> bool:
        """
        Validate that a formula is syntactically correct
        """
        try:
            # Check if formula contains the required {total} variable
            if "{total}" not in formula:
                return False

            # Test with a dummy value
            test_expression = formula.replace("{total}", "100")

            # Validate allowed characters
            if not re.match(r"^[0-9+\-*/.(){} ]+$", test_expression.replace("{total}", "1")):
                return False

            # Try to evaluate with test value
            eval(test_expression)
            return True

        except Exception:
            return False
