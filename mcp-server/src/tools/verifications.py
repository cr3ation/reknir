"""Verification (bokföring) management tools"""
import json
from typing import Any
from mcp.types import Tool, TextContent
from ..client import ReknirClient


def get_verification_tools() -> list[Tool]:
    """Get all verification-related tools"""
    return [
        Tool(
            name="create_verification",
            description=(
                "Create a manual verification (bokföringspost) with debit/credit lines. "
                "Each verification must balance (total debit == total credit). "
                "Use this for expenses, payments, adjustments, etc."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "integer",
                        "description": "Company ID",
                    },
                    "fiscal_year_id": {
                        "type": "integer",
                        "description": "Fiscal year ID",
                    },
                    "transaction_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Transaction date (YYYY-MM-DD)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the transaction",
                    },
                    "series": {
                        "type": "string",
                        "description": "Verification series (e.g. 'A' for general, 'B' for supplier, 'K' for cash)",
                        "default": "A",
                    },
                    "lines": {
                        "type": "array",
                        "description": "Transaction lines (must balance: total debit == total credit)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "account_id": {
                                    "type": "integer",
                                    "description": "Account ID (use search_accounts to find)",
                                },
                                "debit": {
                                    "type": "number",
                                    "description": "Debit amount (0 if credit line)",
                                },
                                "credit": {
                                    "type": "number",
                                    "description": "Credit amount (0 if debit line)",
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Optional line description",
                                },
                            },
                            "required": ["account_id", "debit", "credit"],
                        },
                    },
                },
                "required": ["company_id", "fiscal_year_id", "transaction_date", "description", "lines"],
            },
        ),
        Tool(
            name="list_verifications",
            description="List verifications for a company/fiscal year. Can filter by account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "integer",
                        "description": "Company ID",
                    },
                    "fiscal_year_id": {
                        "type": "integer",
                        "description": "Fiscal year ID (optional)",
                    },
                    "account_id": {
                        "type": "integer",
                        "description": "Filter by account ID (optional)",
                    },
                },
                "required": ["company_id"],
            },
        ),
        Tool(
            name="get_verification",
            description="Get details of a specific verification including all transaction lines.",
            inputSchema={
                "type": "object",
                "properties": {
                    "verification_id": {
                        "type": "integer",
                        "description": "Verification ID",
                    },
                },
                "required": ["verification_id"],
            },
        ),
        Tool(
            name="get_fiscal_year",
            description="Get the current fiscal year for a company.",
            inputSchema={
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "integer",
                        "description": "Company ID",
                    },
                },
                "required": ["company_id"],
            },
        ),
    ]


async def handle_verification_tool(
    name: str, arguments: dict[str, Any], client: ReknirClient
) -> list[TextContent]:
    """Handle verification tool calls"""

    if name == "create_verification":
        # Validate balance
        total_debit = sum(line["debit"] for line in arguments["lines"])
        total_credit = sum(line["credit"] for line in arguments["lines"])
        if abs(total_debit - total_credit) > 0.01:
            return [
                TextContent(
                    type="text",
                    text=f"Error: Verification does not balance. Debit: {total_debit:.2f}, Credit: {total_credit:.2f}",
                )
            ]

        verification = await client.create_verification(arguments)
        result = (
            f"Verification created successfully!\n\n"
            f"ID: {verification['id']}\n"
            f"Number: {verification.get('verification_number', 'N/A')}\n"
            f"Series: {verification.get('series', 'A')}\n"
            f"Date: {verification['transaction_date']}\n"
            f"Description: {verification['description']}\n"
            f"Total: {total_debit:.2f} SEK"
        )
        return [TextContent(type="text", text=result)]

    elif name == "list_verifications":
        verifications = await client.list_verifications(
            company_id=arguments["company_id"],
            fiscal_year_id=arguments.get("fiscal_year_id"),
            account_id=arguments.get("account_id"),
        )

        if not verifications:
            return [TextContent(type="text", text="No verifications found.")]

        result = f"Found {len(verifications)} verification(s):\n\n"
        for v in verifications[:30]:
            result += (
                f"#{v.get('verification_number', v['id'])} "
                f"({v.get('series', 'A')}) "
                f"{v['transaction_date']} - "
                f"{v['description']}\n"
            )

        if len(verifications) > 30:
            result += f"\n... and {len(verifications) - 30} more"

        return [TextContent(type="text", text=result)]

    elif name == "get_verification":
        v = await client.get_verification(arguments["verification_id"])
        result = (
            f"Verification #{v.get('verification_number', v['id'])}\n"
            f"Series: {v.get('series', 'A')}\n"
            f"Date: {v['transaction_date']}\n"
            f"Description: {v['description']}\n\n"
            f"Lines:\n"
        )
        for line in v.get("transaction_lines", v.get("lines", [])):
            debit = line.get("debit", 0)
            credit = line.get("credit", 0)
            desc = line.get("description", "")
            acct = line.get("account_number", line.get("account_id", "?"))
            acct_name = line.get("account_name", "")
            if debit > 0:
                result += f"  D {acct} {acct_name}: {debit:.2f} SEK  {desc}\n"
            if credit > 0:
                result += f"  C {acct} {acct_name}: {credit:.2f} SEK  {desc}\n"
        return [TextContent(type="text", text=result)]

    elif name == "get_fiscal_year":
        fy = await client.get_current_fiscal_year(arguments["company_id"])
        result = (
            f"Current Fiscal Year:\n"
            f"ID: {fy['id']}\n"
            f"Period: {fy['start_date']} - {fy['end_date']}\n"
            f"Year: {fy.get('year', 'N/A')}\n"
            f"Closed: {fy.get('is_closed', False)}"
        )
        return [TextContent(type="text", text=result)]

    return [TextContent(type="text", text=f"Unknown verification tool: {name}")]
