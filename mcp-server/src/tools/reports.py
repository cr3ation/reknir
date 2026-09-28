"""Report tools for viewing financial data"""
import json
from typing import Any
from mcp.types import Tool, TextContent
from ..client import ReknirClient


def get_report_tools() -> list[Tool]:
    """Get all report-related tools"""
    return [
        Tool(
            name="get_account_balances",
            description=(
                "Get account balances for a company. Shows current balance for all accounts "
                "or filtered by type (ASSET, EQUITY_LIABILITY, REVENUE, COST)."
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
                        "description": "Fiscal year ID (optional)",
                    },
                    "account_type": {
                        "type": "string",
                        "description": "Filter by type (optional)",
                        "enum": ["ASSET", "EQUITY_LIABILITY", "REVENUE", "COST"],
                    },
                },
                "required": ["company_id"],
            },
        ),
        Tool(
            name="get_trial_balance",
            description="Get trial balance (saldobalans) for a company and fiscal year.",
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
                },
                "required": ["company_id"],
            },
        ),
        Tool(
            name="get_income_statement",
            description="Get income statement (resultaträkning) for a company and fiscal year.",
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
                },
                "required": ["company_id"],
            },
        ),
        Tool(
            name="get_balance_sheet",
            description="Get balance sheet (balansräkning) for a company and fiscal year.",
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
                },
                "required": ["company_id"],
            },
        ),
    ]


async def handle_report_tool(
    name: str, arguments: dict[str, Any], client: ReknirClient
) -> list[TextContent]:
    """Handle report tool calls"""

    if name == "get_account_balances":
        balances = await client.get_account_balances(
            company_id=arguments["company_id"],
            fiscal_year_id=arguments.get("fiscal_year_id"),
            account_type=arguments.get("account_type"),
        )

        if not balances:
            return [TextContent(type="text", text="No account balances found.")]

        result = "Account Balances:\n\n"
        for acc in balances:
            balance = acc.get("current_balance", 0)
            if abs(balance) > 0.01:
                result += (
                    f"{acc['account_number']} {acc['name']}: "
                    f"{balance:,.2f} SEK\n"
                )

        return [TextContent(type="text", text=result)]

    elif name == "get_trial_balance":
        report = await client.get_trial_balance(
            company_id=arguments["company_id"],
            fiscal_year_id=arguments.get("fiscal_year_id"),
        )
        return [TextContent(type="text", text=json.dumps(report, indent=2, ensure_ascii=False))]

    elif name == "get_income_statement":
        report = await client.get_income_statement(
            company_id=arguments["company_id"],
            fiscal_year_id=arguments.get("fiscal_year_id"),
        )
        return [TextContent(type="text", text=json.dumps(report, indent=2, ensure_ascii=False))]

    elif name == "get_balance_sheet":
        report = await client.get_balance_sheet(
            company_id=arguments["company_id"],
            fiscal_year_id=arguments.get("fiscal_year_id"),
        )
        return [TextContent(type="text", text=json.dumps(report, indent=2, ensure_ascii=False))]

    return [TextContent(type="text", text=f"Unknown report tool: {name}")]
