"""Account management tools"""
from typing import Any
from mcp.types import Tool, TextContent
from ..client import ReknirClient


def get_account_tools() -> list[Tool]:
    """Get all account-related tools"""
    return [
        Tool(
            name="search_accounts",
            description=(
                "Search for accounts by number, name, or type. "
                "Use this to find the correct account ID for categorizing expenses. "
                "Example: search for 'kontorsmaterial', '6071', or type 'expense'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (account number or name)",
                    },
                    "account_type": {
                        "type": "string",
                        "description": "Filter by account type (optional)",
                        "enum": ["asset", "liability", "equity", "revenue", "expense"],
                    },
                    "company_id": {
                        "type": "integer",
                        "description": "Company ID (optional)",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="list_expense_accounts",
            description=(
                "List all expense accounts (cost accounts). "
                "These are accounts used for categorizing supplier invoices and expenses. "
                "Accounts in range 4000-8999."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "integer",
                        "description": "Company ID (optional)",
                    },
                },
            },
        ),
        Tool(
            name="get_account_balance",
            description="Get the current balance of an account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "integer",
                        "description": "Account ID",
                    },
                },
                "required": ["account_id"],
            },
        ),
        Tool(
            name="list_accounts_by_type",
            description="List all accounts of a specific type (asset, liability, revenue, expense, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_type": {
                        "type": "string",
                        "description": "Account type",
                        "enum": ["asset", "liability", "equity", "revenue", "expense"],
                    },
                    "company_id": {
                        "type": "integer",
                        "description": "Company ID (optional)",
                    },
                },
                "required": ["account_type"],
            },
        ),
    ]


async def handle_account_tool(
    name: str, arguments: dict[str, Any], client: ReknirClient
) -> list[TextContent]:
    """Handle account tool calls"""

    if name == "search_accounts":
        query = arguments["query"]
        account_type = arguments.get("account_type")
        company_id = arguments.get("company_id")

        accounts = await client.search_accounts(query, company_id, account_type)

        if not accounts:
            return [
                TextContent(
                    type="text",
                    text=f"No accounts found matching: {query}",
                )
            ]

        result = f"Found {len(accounts)} account(s):\n\n"
        for acc in accounts[:15]:  # Limit to 15
            result += (
                f"{acc['account_number']} - {acc['name']}\n"
                f"  Type: {acc['account_type']}, Balance: {acc.get('current_balance', 0):.2f} SEK "
                f"(ID: {acc['id']})\n\n"
            )

        if len(accounts) > 15:
            result += f"... and {len(accounts) - 15} more\n"

        result += "\nTip: Use the account ID when creating invoice lines."

        return [TextContent(type="text", text=result)]

    elif name == "list_expense_accounts":
        company_id = arguments.get("company_id")
        accounts = await client.list_accounts(company_id, account_type="expense")

        if not accounts:
            return [TextContent(type="text", text="No expense accounts found.")]

        # Group by common categories
        categories = {
            "4": "Cost of Goods Sold (4000-4999)",
            "5": "Facility Costs (5000-5999)",
            "6": "Operating Costs (6000-6999)",
            "7": "Personnel Costs (7000-7999)",
            "8": "Other Costs (8000-8999)",
        }

        result = "Expense Accounts:\n\n"
        current_category = None

        for acc in accounts[:50]:  # Limit to 50
            acc_num_str = str(acc["account_number"])
            category = acc_num_str[0] if acc_num_str else "9"

            if category != current_category:
                current_category = category
                if category in categories:
                    result += f"\n{categories[category]}\n" + "-" * 40 + "\n"

            result += f"{acc['account_number']} - {acc['name']}\n"

        if len(accounts) > 50:
            result += f"\n... and {len(accounts) - 50} more expense accounts"

        return [TextContent(type="text", text=result)]

    elif name == "get_account_balance":
        account_id = arguments["account_id"]
        account = await client.get_account(account_id)

        result = (
            f"Account: {account['account_number']} - {account['name']}\n"
            f"Type: {account['account_type']}\n"
            f"Current Balance: {account.get('current_balance', 0):.2f} SEK\n"
            f"Opening Balance: {account.get('opening_balance', 0):.2f} SEK\n"
            f"Active: {'Yes' if account.get('active', True) else 'No'}"
        )

        return [TextContent(type="text", text=result)]

    elif name == "list_accounts_by_type":
        account_type = arguments["account_type"]
        company_id = arguments.get("company_id")
        accounts = await client.list_accounts(company_id, account_type=account_type)

        if not accounts:
            return [
                TextContent(
                    type="text",
                    text=f"No {account_type} accounts found.",
                )
            ]

        result = f"{account_type.title()} Accounts ({len(accounts)}):\n\n"
        for acc in accounts[:30]:  # Limit to 30
            result += (
                f"{acc['account_number']} - {acc['name']}\n"
                f"  Balance: {acc.get('current_balance', 0):.2f} SEK\n"
            )

        if len(accounts) > 30:
            result += f"\n... and {len(accounts) - 30} more"

        return [TextContent(type="text", text=result)]

    return [TextContent(type="text", text=f"Unknown account tool: {name}")]
