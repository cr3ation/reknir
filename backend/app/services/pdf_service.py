import os
from pathlib import Path

from fastapi import HTTPException
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app.models.company import Company
from app.models.customer import Customer
from app.models.invoice import Invoice


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
    import traceback

    try:
        # Test with simple HTML first
        simple_html = "<html><body><h1>Test PDF</h1></body></html>"

        print("Attempting to create simple PDF...")
        test_pdf = HTML(string=simple_html)
        print("HTML object created successfully")

        test_bytes = test_pdf.write_pdf()
        print(f"Simple PDF generated: {len(test_bytes)} bytes")

        # Now try with template
        template_dir = Path(__file__).parent.parent / "templates"
        print(f"Template directory: {template_dir}")

        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template("invoice_template.html")
        print("Template loaded successfully")

        # Check for company logo
        logo_data = None
        if company.logo_filename:
            logo_path = f"/app/uploads/logos/{company.logo_filename}"
            if os.path.exists(logo_path):
                import base64

                with open(logo_path, "rb") as logo_file:
                    logo_data = base64.b64encode(logo_file.read()).decode("utf-8")
                    # Determine MIME type
                    extension = company.logo_filename.split(".")[-1].lower()
                    mime_type = "image/png" if extension == "png" else "image/jpeg"
                    logo_data = f"data:{mime_type};base64,{logo_data}"

        html_content = template.render(invoice=invoice, customer=customer, company=company, company_logo=logo_data)
        print(f"Template rendered: {len(html_content)} chars")

        # Generate PDF
        pdf_bytes = HTML(string=html_content).write_pdf()
        print(f"Invoice PDF generated: {len(pdf_bytes)} bytes")

        return pdf_bytes
    except Exception as e:
        print(f"PDF generation error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}") from e


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
    with open(filepath, "wb") as f:
        f.write(pdf_bytes)

    return filepath
