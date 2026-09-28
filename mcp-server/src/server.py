"""Reknir MCP Server - Main server implementation"""
import os
import sys
import asyncio
from dotenv import load_dotenv
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

from .client import ReknirClient
from .tools.suppliers import get_supplier_tools, handle_supplier_tool
from .tools.invoices import get_invoice_tools, handle_invoice_tool
from .tools.accounts import get_account_tools, handle_account_tool
from .tools.companies import get_company_tools, handle_company_tool
from .tools.verifications import get_verification_tools, handle_verification_tool
from .tools.reports import get_report_tools, handle_report_tool

# Load environment variables
load_dotenv()


def log(msg: str):
    """Log to stderr (stdout is used by MCP protocol)"""
    print(msg, file=sys.stderr, flush=True)


# Initialize server
app = Server("reknir")

# Initialize client (will be created in serve())
client: ReknirClient | None = None


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools"""
    tools = []
    tools.extend(get_company_tools())
    tools.extend(get_supplier_tools())
    tools.extend(get_invoice_tools())
    tools.extend(get_account_tools())
    tools.extend(get_verification_tools())
    tools.extend(get_report_tools())
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    if client is None:
        return [
            TextContent(
                type="text",
                text="Error: Reknir client not initialized. Please check your configuration.",
            )
        ]

    try:
        # Route to appropriate tool handler
        if name in ["get_company_info", "list_companies"]:
            return await handle_company_tool(name, arguments, client)

        elif name in ["find_supplier", "create_supplier", "list_suppliers"]:
            return await handle_supplier_tool(name, arguments, client)

        elif name in [
            "create_supplier_invoice",
            "register_invoice",
            "mark_invoice_paid",
            "list_supplier_invoices",
            "get_invoice_details",
        ]:
            return await handle_invoice_tool(name, arguments, client)

        elif name in [
            "search_accounts",
            "list_expense_accounts",
            "get_account_balance",
            "list_accounts_by_type",
        ]:
            return await handle_account_tool(name, arguments, client)

        elif name in [
            "create_verification",
            "list_verifications",
            "get_verification",
            "get_fiscal_year",
        ]:
            return await handle_verification_tool(name, arguments, client)

        elif name in [
            "get_account_balances",
            "get_trial_balance",
            "get_income_statement",
            "get_balance_sheet",
        ]:
            return await handle_report_tool(name, arguments, client)

        else:
            return [
                TextContent(
                    type="text",
                    text=f"Unknown tool: {name}",
                )
            ]

    except Exception as e:
        error_msg = f"Error calling tool '{name}': {str(e)}"
        log(f"[ERROR] {error_msg}")
        return [
            TextContent(
                type="text",
                text=error_msg,
            )
        ]


async def serve():
    """Run the MCP server"""
    global client

    # Initialize Reknir client
    api_url = os.getenv("REKNIR_API_URL", "http://localhost:8000")
    company_id = int(os.getenv("REKNIR_COMPANY_ID", "1"))

    log(f"[INFO] Initializing Reknir MCP Server")
    log(f"[INFO] API URL: {api_url}")
    log(f"[INFO] Default Company ID: {company_id}")

    client = ReknirClient(base_url=api_url, company_id=company_id)

    try:
        # Test connection
        company = await client.get_company()
        log(f"[INFO] Connected to Reknir: {company['name']}")
        log(f"[INFO] Server ready!")

        # Run the server
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())

    finally:
        if client:
            await client.close()
            log("[INFO] Reknir client closed")


def main():
    """Entry point for the server"""
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        log("\n[INFO] Server stopped by user")
    except Exception as e:
        log(f"[ERROR] Server error: {e}")
        raise


if __name__ == "__main__":
    main()
