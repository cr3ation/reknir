"""Supplier invoice management tools"""
from typing import Any
from mcp.types import Tool, TextContent
from ..client import ReknirClient


def get_invoice_tools() -> list[Tool]:
    """Get all invoice-related tools"""
    return [
        Tool(
            name="create_supplier_invoice",
            description=(
                "Create a supplier invoice (incoming invoice) with line items. "
                "This is used when you receive an invoice from a supplier. "
                "The invoice will be created in 'draft' status initially."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "integer",
                        "description": "Company ID",
                    },
                    "supplier_id": {
                        "type": "integer",
                        "description": "Supplier ID (use find_supplier to get this)",
                    },
                    "invoice_number": {
                        "type": "string",
                        "description": "Invoice number from the supplier",
                    },
                    "invoice_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Invoice date (YYYY-MM-DD)",
                    },
                    "due_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Due date (YYYY-MM-DD)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description/notes",
                    },
                    "lines": {
                        "type": "array",
                        "description": "Invoice line items",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {
                                    "type": "string",
                                    "description": "Line item description",
                                },
                                "quantity": {
                                    "type": "number",
                                    "description": "Quantity",
                                },
                                "unit_price": {
                                    "type": "number",
                                    "description": "Unit price (excluding VAT)",
                                },
                                "vat_rate": {
                                    "type": "number",
                                    "description": "VAT rate (0, 6, 12, or 25)",
                                    "enum": [0, 6, 12, 25],
                                },
                                "account_id": {
                                    "type": "integer",
                                    "description": "Account ID for this expense (use search_accounts to find)",
                                },
                            },
                            "required": ["description", "quantity", "unit_price", "vat_rate", "account_id"],
                        },
                    },
                },
                "required": ["company_id", "supplier_id", "invoice_number", "invoice_date", "lines"],
            },
        ),
        Tool(
            name="register_invoice",
            description=(
                "Register (book) a supplier invoice. "
                "This creates accounting entries (verifications) and moves the invoice to 'sent' status. "
                "Use after creating the invoice."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "invoice_id": {
                        "type": "integer",
                        "description": "Invoice ID to register",
                    },
                },
                "required": ["invoice_id"],
            },
        ),
        Tool(
            name="mark_invoice_paid",
            description=(
                "Mark a supplier invoice as paid. "
                "This creates a payment verification and moves the invoice to 'paid' status. "
                "Use after the invoice has been paid."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "invoice_id": {
                        "type": "integer",
                        "description": "Invoice ID to mark as paid",
                    },
                    "paid_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Payment date (YYYY-MM-DD)",
                    },
                    "paid_amount": {
                        "type": "number",
                        "description": "Amount paid (optional, uses invoice total if not provided)",
                    },
                },
                "required": ["invoice_id", "paid_date"],
            },
        ),
        Tool(
            name="list_supplier_invoices",
            description="List supplier invoices. Can filter by supplier or status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "integer",
                        "description": "Company ID (optional)",
                    },
                    "supplier_id": {
                        "type": "integer",
                        "description": "Filter by supplier ID (optional)",
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status (optional)",
                        "enum": ["draft", "sent", "paid", "partial", "overdue", "cancelled"],
                    },
                },
            },
        ),
        Tool(
            name="get_invoice_details",
            description="Get detailed information about a specific supplier invoice, including all line items.",
            inputSchema={
                "type": "object",
                "properties": {
                    "invoice_id": {
                        "type": "integer",
                        "description": "Invoice ID",
                    },
                },
                "required": ["invoice_id"],
            },
        ),
    ]


async def handle_invoice_tool(
    name: str, arguments: dict[str, Any], client: ReknirClient
) -> list[TextContent]:
    """Handle invoice tool calls"""

    if name == "create_supplier_invoice":
        invoice = await client.create_supplier_invoice(arguments)

        # Format the response
        total_net = sum(
            line["quantity"] * line["unit_price"] for line in arguments["lines"]
        )
        total_vat = sum(
            line["quantity"] * line["unit_price"] * line["vat_rate"] / 100
            for line in arguments["lines"]
        )
        total = total_net + total_vat

        result = (
            f"✓ Supplier invoice created successfully!\n\n"
            f"Invoice ID: {invoice['id']}\n"
            f"Invoice Number: {invoice['invoice_number']}\n"
            f"Supplier: {invoice.get('supplier_name', 'N/A')}\n"
            f"Date: {invoice['invoice_date']}\n"
            f"Status: {invoice['status']}\n\n"
            f"Lines: {len(arguments['lines'])}\n"
            f"Total (excl. VAT): {total_net:.2f} SEK\n"
            f"VAT: {total_vat:.2f} SEK\n"
            f"Total (incl. VAT): {total:.2f} SEK\n\n"
            f"Next step: Use 'register_invoice' to book this invoice."
        )
        return [TextContent(type="text", text=result)]

    elif name == "register_invoice":
        invoice = await client.register_invoice(arguments["invoice_id"])
        return [
            TextContent(
                type="text",
                text=(
                    f"✓ Invoice registered (booked) successfully!\n\n"
                    f"Invoice: {invoice['invoice_number']}\n"
                    f"Status: {invoice['status']}\n"
                    f"Verification created: Yes\n\n"
                    f"The invoice is now in accounts payable."
                ),
            )
        ]

    elif name == "mark_invoice_paid":
        invoice = await client.mark_invoice_paid(
            arguments["invoice_id"],
            arguments["paid_date"],
            arguments.get("paid_amount"),
        )
        return [
            TextContent(
                type="text",
                text=(
                    f"✓ Invoice marked as paid!\n\n"
                    f"Invoice: {invoice['invoice_number']}\n"
                    f"Status: {invoice['status']}\n"
                    f"Paid date: {invoice.get('paid_date', 'N/A')}\n"
                    f"Amount: {invoice.get('paid_amount', invoice.get('total_amount', 0)):.2f} SEK"
                ),
            )
        ]

    elif name == "list_supplier_invoices":
        invoices = await client.list_supplier_invoices(
            company_id=arguments.get("company_id"),
            supplier_id=arguments.get("supplier_id"),
            status=arguments.get("status"),
        )

        if not invoices:
            return [TextContent(type="text", text="No invoices found.")]

        result = f"Found {len(invoices)} invoice(s):\n\n"
        for inv in invoices[:20]:  # Limit to 20
            status_emoji = {
                "draft": "📝",
                "sent": "📤",
                "paid": "✅",
                "partial": "⚠️",
                "overdue": "🔴",
                "cancelled": "❌",
            }.get(inv.get("status", ""), "")

            result += (
                f"{status_emoji} {inv['invoice_number']} - "
                f"{inv.get('supplier_name', 'Unknown')} - "
                f"{inv.get('total_amount', 0):.2f} SEK "
                f"({inv.get('status', 'unknown')})\n"
            )

        if len(invoices) > 20:
            result += f"\n... and {len(invoices) - 20} more"

        return [TextContent(type="text", text=result)]

    elif name == "get_invoice_details":
        invoice = await client.get_supplier_invoice(arguments["invoice_id"])

        result = (
            f"Invoice Details:\n\n"
            f"Invoice Number: {invoice['invoice_number']}\n"
            f"Supplier: {invoice.get('supplier_name', 'N/A')}\n"
            f"Date: {invoice['invoice_date']}\n"
            f"Due Date: {invoice.get('due_date', 'N/A')}\n"
            f"Status: {invoice['status']}\n"
            f"Description: {invoice.get('description', 'N/A')}\n\n"
            f"Line Items:\n"
        )

        for idx, line in enumerate(invoice.get("lines", []), 1):
            line_total = line["quantity"] * line["unit_price"]
            result += (
                f"{idx}. {line['description']}\n"
                f"   {line['quantity']} × {line['unit_price']:.2f} SEK "
                f"(VAT {line['vat_rate']}%) = {line_total:.2f} SEK\n"
            )

        result += (
            f"\nTotal (excl. VAT): {invoice.get('net_amount', 0):.2f} SEK\n"
            f"VAT: {invoice.get('vat_amount', 0):.2f} SEK\n"
            f"Total (incl. VAT): {invoice.get('total_amount', 0):.2f} SEK"
        )

        return [TextContent(type="text", text=result)]

    return [TextContent(type="text", text=f"Unknown invoice tool: {name}")]
