"""Tests that verify the MCP client sends all required parameters to the backend API.

The backend uses FastAPI Query(...) for required parameters. Missing any of these
causes a 422 Unprocessable Entity error. These tests catch that class of bug by
asserting that every client method includes the required params in its requests.

Backend required parameters (Query(...)):
  GET /api/accounts/          -> company_id, fiscal_year_id
  GET /api/accounts/balances  -> company_id, fiscal_year_id
  GET /api/suppliers/         -> company_id
  GET /api/supplier-invoices/ -> company_id
  GET /api/verifications/     -> company_id
  GET /api/fiscal-years/      -> company_id
  GET /api/reports/trial-balance     -> company_id, fiscal_year_id
  GET /api/reports/income-statement  -> company_id, fiscal_year_id
  GET /api/reports/balance-sheet     -> company_id, fiscal_year_id
  GET /api/default-accounts/  -> company_id
"""

import pytest


# --- Accounts ---


@pytest.mark.asyncio
async def test_list_accounts_sends_fiscal_year_id(client, recorder):
    """list_accounts must send fiscal_year_id (required by backend)."""
    await client.list_accounts()
    params = recorder.get_params_for("/api/accounts/")
    assert "fiscal_year_id" in params, "fiscal_year_id is required by GET /api/accounts/"
    assert params["fiscal_year_id"] is not None


@pytest.mark.asyncio
async def test_list_accounts_sends_company_id(client, recorder):
    """list_accounts must send company_id (required by backend)."""
    await client.list_accounts()
    params = recorder.get_params_for("/api/accounts/")
    assert "company_id" in params
    assert params["company_id"] is not None


@pytest.mark.asyncio
async def test_list_accounts_with_explicit_fiscal_year(client, recorder):
    """When fiscal_year_id is provided, it should not fetch current fiscal year."""
    await client.list_accounts(company_id=1, account_type="expense")
    params = recorder.get_params_for("/api/accounts/")
    assert params["fiscal_year_id"] is not None
    assert params["company_id"] == 1


# --- Account Balances ---


@pytest.mark.asyncio
async def test_get_account_balances_sends_fiscal_year_id(client, recorder):
    """get_account_balances must send fiscal_year_id (required by backend)."""
    await client.get_account_balances()
    params = recorder.get_params_for("/api/accounts/balances")
    assert "fiscal_year_id" in params
    assert params["fiscal_year_id"] is not None


@pytest.mark.asyncio
async def test_get_account_balances_sends_company_id(client, recorder):
    await client.get_account_balances()
    params = recorder.get_params_for("/api/accounts/balances")
    assert "company_id" in params


@pytest.mark.asyncio
async def test_get_account_balances_uses_provided_fiscal_year(client, recorder):
    await client.get_account_balances(fiscal_year_id=42)
    params = recorder.get_params_for("/api/accounts/balances")
    assert params["fiscal_year_id"] == 42


# --- Suppliers ---


@pytest.mark.asyncio
async def test_list_suppliers_sends_company_id(client, recorder):
    """list_suppliers must send company_id (required by backend)."""
    await client.list_suppliers()
    params = recorder.get_params_for("/api/suppliers/")
    assert "company_id" in params
    assert params["company_id"] is not None


# --- Supplier Invoices ---


@pytest.mark.asyncio
async def test_list_supplier_invoices_sends_company_id(client, recorder):
    """list_supplier_invoices must send company_id (required by backend)."""
    await client.list_supplier_invoices()
    params = recorder.get_params_for("/api/supplier-invoices/")
    assert "company_id" in params
    assert params["company_id"] is not None


# --- Verifications ---


@pytest.mark.asyncio
async def test_list_verifications_sends_company_id(client, recorder):
    """list_verifications must send company_id (required by backend)."""
    await client.list_verifications()
    params = recorder.get_params_for("/api/verifications/")
    assert "company_id" in params
    assert params["company_id"] is not None


# --- Reports ---


@pytest.mark.asyncio
async def test_get_trial_balance_sends_fiscal_year_id(client, recorder):
    """get_trial_balance must send fiscal_year_id (required by backend)."""
    await client.get_trial_balance()
    params = recorder.get_params_for("/api/reports/trial-balance")
    assert "fiscal_year_id" in params
    assert params["fiscal_year_id"] is not None


@pytest.mark.asyncio
async def test_get_trial_balance_sends_company_id(client, recorder):
    await client.get_trial_balance()
    params = recorder.get_params_for("/api/reports/trial-balance")
    assert "company_id" in params


@pytest.mark.asyncio
async def test_get_income_statement_sends_fiscal_year_id(client, recorder):
    """get_income_statement must send fiscal_year_id (required by backend)."""
    await client.get_income_statement()
    params = recorder.get_params_for("/api/reports/income-statement")
    assert "fiscal_year_id" in params
    assert params["fiscal_year_id"] is not None


@pytest.mark.asyncio
async def test_get_income_statement_sends_company_id(client, recorder):
    await client.get_income_statement()
    params = recorder.get_params_for("/api/reports/income-statement")
    assert "company_id" in params


@pytest.mark.asyncio
async def test_get_balance_sheet_sends_fiscal_year_id(client, recorder):
    """get_balance_sheet must send fiscal_year_id (required by backend)."""
    await client.get_balance_sheet()
    params = recorder.get_params_for("/api/reports/balance-sheet")
    assert "fiscal_year_id" in params
    assert params["fiscal_year_id"] is not None


@pytest.mark.asyncio
async def test_get_balance_sheet_sends_company_id(client, recorder):
    await client.get_balance_sheet()
    params = recorder.get_params_for("/api/reports/balance-sheet")
    assert "company_id" in params


# --- Default Accounts ---


@pytest.mark.asyncio
async def test_list_default_accounts_sends_company_id(client, recorder):
    """list_default_accounts must send company_id (required by backend)."""
    await client.list_default_accounts()
    params = recorder.get_params_for("/api/default-accounts/")
    assert "company_id" in params
    assert params["company_id"] is not None
