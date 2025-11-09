from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from pathlib import Path
import os
from typing import BinaryIO
from app.models.invoice import Invoice
from app.models.customer import Customer
from app.models.company import Company


def generate_invoice_pdf(invoice: Invoice, customer: Customer, company: Company) -> bytes:
    """
    Generate a PDF for a Swedish invoice

    Args:
        invoice: Invoice model instance with invoice_lines loaded
        customer: Customer model instance
        company: Company model instance

    Returns:
        bytes: PDF file content
    """

    # Get template directory
    template_dir = Path(__file__).parent.parent / "templates"

    # Setup Jinja2 environment
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("invoice_template.html")

    # Render HTML with data
    html_content = template.render(
        invoice=invoice,
        customer=customer,
        company=company
    )

    # Generate PDF from HTML
    pdf_bytes = HTML(string=html_content).write_pdf()

    return pdf_bytes


def save_invoice_pdf(invoice: Invoice, customer: Customer, company: Company, output_dir: str = "/tmp") -> str:
    """
    Generate and save invoice PDF to file

    Args:
        invoice: Invoice model instance
        customer: Customer model instance
        company: Company model instance
        output_dir: Directory to save PDF (default: /tmp)

    Returns:
        str: Path to saved PDF file
    """

    pdf_bytes = generate_invoice_pdf(invoice, customer, company)

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Generate filename
    filename = f"faktura_{invoice.invoice_series}{invoice.invoice_number}.pdf"
    filepath = os.path.join(output_dir, filename)

    # Save PDF
    with open(filepath, 'wb') as f:
        f.write(pdf_bytes)

    return filepath
