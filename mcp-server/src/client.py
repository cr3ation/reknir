"""Reknir API Client for MCP Server"""
import os
import time
from typing import Any, Optional
import httpx


class ReknirClient:
    """Client for interacting with Reknir API"""

    def __init__(self, base_url: Optional[str] = None, company_id: Optional[int] = None, api_key: Optional[str] = None):
        self.base_url = base_url or os.getenv("REKNIR_API_URL", "http://localhost:8000")
        self.company_id = company_id or int(os.getenv("REKNIR_COMPANY_ID", "1"))
        self.api_key = api_key or os.getenv("REKNIR_API_KEY", "")
        self._token: Optional[str] = None
        self._token_expires_at: float = 0
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
            headers={"Content-Type": "application/json"},
        )

    async def _ensure_token(self):
        """Exchange API key for JWT if needed"""
        if not self.api_key:
            return
        # Refresh if token expires within 5 minutes
        if self._token and time.time() < self._token_expires_at - 300:
            return
        response = await self.client.post(
            "/api/auth/token/api-key",
            json={"api_key": self.api_key},
        )
        response.raise_for_status()
        data = response.json()
        self._token = data["access_token"]
        # Token is valid for 1 hour, track expiry
        self._token_expires_at = time.time() + 3600
        self.client.headers["Authorization"] = f"Bearer {self._token}"
        import sys
        print("[INFO] Authenticated with API key", file=sys.stderr, flush=True)

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    async def _get(self, url: str, **kwargs) -> httpx.Response:
        await self._ensure_token()
        response = await self.client.get(url, **kwargs)
        response.raise_for_status()
        return response

    async def _post(self, url: str, **kwargs) -> httpx.Response:
        await self._ensure_token()
        response = await self.client.post(url, **kwargs)
        response.raise_for_status()
        return response

    # Companies
    async def get_company(self, company_id: Optional[int] = None) -> dict[str, Any]:
        """Get company information"""
        cid = company_id or self.company_id
        response = await self._get(f"/api/companies/{cid}")
        return response.json()

    async def list_companies(self) -> list[dict[str, Any]]:
        """List all companies"""
        response = await self._get("/api/companies/")
        response.raise_for_status()
        return response.json()

    # Suppliers
    async def list_suppliers(
        self, company_id: Optional[int] = None, active_only: bool = True
    ) -> list[dict[str, Any]]:
        """List suppliers"""
        cid = company_id or self.company_id
        response = await self._get("/api/suppliers/", params={"company_id": cid, "active_only": active_only})
        return response.json()

    async def get_supplier(self, supplier_id: int) -> dict[str, Any]:
        """Get supplier by ID"""
        response = await self._get(f"/api/suppliers/{supplier_id}")
        return response.json()

    async def create_supplier(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new supplier"""
        response = await self._post("/api/suppliers/", json=data)
        return response.json()

    async def find_supplier_by_org_number(
        self, org_number: str, company_id: Optional[int] = None
    ) -> Optional[dict[str, Any]]:
        """Find supplier by organization number"""
        suppliers = await self.list_suppliers(company_id, active_only=False)
        for supplier in suppliers:
            if supplier.get("org_number") == org_number:
                return supplier
        return None

    # Accounts
    async def list_accounts(
        self,
        company_id: Optional[int] = None,
        account_type: Optional[str] = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """List accounts"""
        cid = company_id or self.company_id
        fiscal_year = await self.get_current_fiscal_year(cid)
        params: dict[str, Any] = {
            "company_id": cid,
            "fiscal_year_id": fiscal_year["id"],
            "active_only": active_only,
        }
        if account_type:
            params["account_type"] = account_type
        response = await self._get("/api/accounts/", params=params)
        return response.json()

    async def search_accounts(
        self,
        query: str,
        company_id: Optional[int] = None,
        account_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Search accounts by number or name"""
        accounts = await self.list_accounts(company_id, account_type)
        query_lower = query.lower()
        return [
            acc
            for acc in accounts
            if query_lower in str(acc["account_number"]).lower()
            or query_lower in acc["name"].lower()
        ]

    async def get_account(self, account_id: int) -> dict[str, Any]:
        """Get account by ID"""
        response = await self._get(f"/api/accounts/{account_id}")
        return response.json()

    # Supplier Invoices
    async def list_supplier_invoices(
        self,
        company_id: Optional[int] = None,
        supplier_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List supplier invoices"""
        cid = company_id or self.company_id
        params: dict[str, Any] = {"company_id": cid}
        if supplier_id:
            params["supplier_id"] = supplier_id
        if status:
            params["status"] = status
        response = await self._get("/api/supplier-invoices/", params=params)
        return response.json()

    async def get_supplier_invoice(self, invoice_id: int) -> dict[str, Any]:
        """Get supplier invoice by ID"""
        response = await self._get(f"/api/supplier-invoices/{invoice_id}")
        return response.json()

    async def create_supplier_invoice(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a supplier invoice"""
        response = await self._post("/api/supplier-invoices/", json=data)
        return response.json()

    async def register_invoice(self, invoice_id: int) -> dict[str, Any]:
        """Register (book) a supplier invoice"""
        response = await self._post(f"/api/supplier-invoices/{invoice_id}/register")
        return response.json()

    async def mark_invoice_paid(
        self, invoice_id: int, paid_date: str, paid_amount: Optional[float] = None
    ) -> dict[str, Any]:
        """Mark invoice as paid"""
        data: dict[str, Any] = {"paid_date": paid_date}
        if paid_amount:
            data["paid_amount"] = paid_amount
        response = await self._post(f"/api/supplier-invoices/{invoice_id}/mark-paid", json=data)
        return response.json()

    # Default Accounts
    async def list_default_accounts(
        self, company_id: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """List default accounts"""
        cid = company_id or self.company_id
        response = await self._get("/api/default-accounts/", params={"company_id": cid})
        return response.json()

    # Verifications
    async def create_verification(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a verification (bokföringspost)"""
        response = await self._post("/api/verifications/", json=data)
        return response.json()

    async def list_verifications(
        self,
        company_id: Optional[int] = None,
        fiscal_year_id: Optional[int] = None,
        account_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """List verifications"""
        cid = company_id or self.company_id
        params: dict[str, Any] = {"company_id": cid}
        if fiscal_year_id:
            params["fiscal_year_id"] = fiscal_year_id
        if account_id:
            params["account_id"] = account_id
        response = await self._get("/api/verifications/", params=params)
        return response.json()

    async def get_verification(self, verification_id: int) -> dict[str, Any]:
        """Get a specific verification"""
        response = await self._get(f"/api/verifications/{verification_id}")
        return response.json()

    # Fiscal Years
    async def get_current_fiscal_year(self, company_id: Optional[int] = None) -> dict[str, Any]:
        """Get the current fiscal year for a company"""
        cid = company_id or self.company_id
        response = await self._get(f"/api/fiscal-years/current/by-company/{cid}")
        return response.json()

    # Reports
    async def get_account_balances(
        self,
        company_id: Optional[int] = None,
        fiscal_year_id: Optional[int] = None,
        account_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get account balances"""
        cid = company_id or self.company_id
        if not fiscal_year_id:
            fiscal_year = await self.get_current_fiscal_year(cid)
            fiscal_year_id = fiscal_year["id"]
        params: dict[str, Any] = {"company_id": cid, "fiscal_year_id": fiscal_year_id}
        if account_type:
            params["account_type"] = account_type
        response = await self._get("/api/accounts/balances", params=params)
        return response.json()

    async def get_trial_balance(
        self, company_id: Optional[int] = None, fiscal_year_id: Optional[int] = None
    ) -> dict[str, Any]:
        """Get trial balance"""
        cid = company_id or self.company_id
        if not fiscal_year_id:
            fiscal_year = await self.get_current_fiscal_year(cid)
            fiscal_year_id = fiscal_year["id"]
        params: dict[str, Any] = {"company_id": cid, "fiscal_year_id": fiscal_year_id}
        response = await self._get("/api/reports/trial-balance", params=params)
        return response.json()

    async def get_income_statement(
        self, company_id: Optional[int] = None, fiscal_year_id: Optional[int] = None
    ) -> dict[str, Any]:
        """Get income statement"""
        cid = company_id or self.company_id
        if not fiscal_year_id:
            fiscal_year = await self.get_current_fiscal_year(cid)
            fiscal_year_id = fiscal_year["id"]
        params: dict[str, Any] = {"company_id": cid, "fiscal_year_id": fiscal_year_id}
        response = await self._get("/api/reports/income-statement", params=params)
        return response.json()

    async def get_balance_sheet(
        self, company_id: Optional[int] = None, fiscal_year_id: Optional[int] = None
    ) -> dict[str, Any]:
        """Get balance sheet"""
        cid = company_id or self.company_id
        if not fiscal_year_id:
            fiscal_year = await self.get_current_fiscal_year(cid)
            fiscal_year_id = fiscal_year["id"]
        params: dict[str, Any] = {"company_id": cid, "fiscal_year_id": fiscal_year_id}
        response = await self._get("/api/reports/balance-sheet", params=params)
        return response.json()
