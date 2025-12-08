"""Company management tools"""
from typing import Any
from mcp.types import Tool, TextContent
from ..client import ReknirClient


def get_company_tools() -> list[Tool]:
    """Get all company-related tools"""
    return [
        Tool(
            name="get_company_info",
            description=(
                "Get information about the current company or a specific company. "
                "Use this to get the default company ID for other operations."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "integer",
                        "description": "Company ID (optional, uses default if not provided)",
                    },
                },
            },
        ),
        Tool(
            name="list_companies",
            description="List all companies in the system. Useful for multi-company setups.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


async def handle_company_tool(
    name: str, arguments: dict[str, Any], client: ReknirClient
) -> list[TextContent]:
    """Handle company tool calls"""

    if name == "get_company_info":
        company_id = arguments.get("company_id")
        company = await client.get_company(company_id)

        result = (
            f"Company Information:\n\n"
            f"ID: {company['id']}\n"
            f"Name: {company['name']}\n"
            f"Org. Number: {company['org_number']}\n"
            f"Address: {company.get('address', 'N/A')}\n"
            f"Postal Code: {company.get('postal_code', 'N/A')}\n"
            f"City: {company.get('city', 'N/A')}\n"
            f"Phone: {company.get('phone', 'N/A')}\n"
            f"Email: {company.get('email', 'N/A')}\n\n"
            f"Fiscal Year: {company['fiscal_year_start']} to {company['fiscal_year_end']}\n"
            f"Accounting Basis: {company['accounting_basis']}\n"
            f"VAT Reporting: {company['vat_reporting_period']}\n\n"
            f"Use company_id={company['id']} in other tool calls."
        )

        return [TextContent(type="text", text=result)]

    elif name == "list_companies":
        companies = await client.list_companies()

        if not companies:
            return [TextContent(type="text", text="No companies found.")]

        result = f"Found {len(companies)} company/companies:\n\n"
        for comp in companies:
            result += (
                f"• {comp['name']} (ID: {comp['id']})\n"
                f"  Org.nr: {comp['org_number']}\n"
                f"  City: {comp.get('city', 'N/A')}\n\n"
            )

        return [TextContent(type="text", text=result)]

    return [TextContent(type="text", text=f"Unknown company tool: {name}")]
