"""Tests that verify MCP tool handlers don't raise exceptions.

Each tool handler is called with minimal valid arguments. The client is mocked
so no real API calls are made. The test passes if the handler returns TextContent
without raising (i.e., no 422 errors from missing required params).
"""

import pytest
from src.tools.accounts import handle_account_tool
from src.tools.companies import handle_company_tool
from src.tools.invoices import handle_invoice_tool
from src.tools.reports import handle_report_tool
from src.tools.suppliers import handle_supplier_tool
from src.tools.verifications import handle_verification_tool


@pytest.mark.asyncio
async def test_search_accounts(client):
    result = await handle_account_tool("search_accounts", {"query": "kontorsmaterial"}, client)
    assert len(result) > 0
    assert result[0].type == "text"


@pytest.mark.asyncio
async def test_list_expense_accounts(client):
    result = await handle_account_tool("list_expense_accounts", {}, client)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_list_accounts_by_type(client):
    result = await handle_account_tool("list_accounts_by_type", {"account_type": "expense"}, client)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_get_company_info(client):
    result = await handle_company_tool("get_company_info", {}, client)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_list_companies(client):
    result = await handle_company_tool("list_companies", {}, client)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_find_supplier_by_name(client):
    result = await handle_supplier_tool("find_supplier", {"name": "Loopia"}, client)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_list_suppliers(client):
    result = await handle_supplier_tool("list_suppliers", {}, client)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_list_supplier_invoices(client):
    result = await handle_invoice_tool("list_supplier_invoices", {}, client)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_get_trial_balance(client):
    result = await handle_report_tool("get_trial_balance", {"company_id": 1}, client)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_get_income_statement(client):
    result = await handle_report_tool("get_income_statement", {"company_id": 1}, client)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_get_balance_sheet(client):
    result = await handle_report_tool("get_balance_sheet", {"company_id": 1}, client)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_get_account_balances(client):
    result = await handle_report_tool("get_account_balances", {"company_id": 1}, client)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_list_verifications(client):
    result = await handle_verification_tool("list_verifications", {"company_id": 1}, client)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_get_fiscal_year(client):
    result = await handle_verification_tool("get_fiscal_year", {"company_id": 1}, client)
    assert len(result) > 0
    assert "2026" in result[0].text
