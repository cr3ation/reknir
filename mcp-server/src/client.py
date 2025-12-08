"""Reknir API Client for MCP Server"""
import os
from typing import Any, Optional
import httpx
from pydantic import BaseModel


class ReknirClient:
    """Client for interacting with Reknir API"""

    def __init__(self, base_url: Optional[str] = None, company_id: Optional[int] = None):
        self.base_url = base_url or os.getenv("REKNIR_API_URL", "http://localhost:8000")
        self.company_id = company_id or int(os.getenv("REKNIR_COMPANY_ID", "1"))
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
            headers={"Content-Type": "application/json"},
        )

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    # Companies
    async def get_company(self, company_id: Optional[int] = None) -> dict[str, Any]:
        """Get company information"""
        cid = company_id or self.company_id
        response = await self.client.get(f"/api/companies/{cid}")
        response.raise_for_status()
        return response.json()

    async def list_companies(self) -> list[dict[str, Any]]:
        """List all companies"""
        response = await self.client.get("/api/companies/")
        response.raise_for_status()
        return response.json()

    # Suppliers
    async def list_suppliers(
        self, company_id: Optional[int] = None, active_only: bool = True
    ) -> list[dict[str, Any]]:
        """List suppliers"""
        cid = company_id or self.company_id
        response = await self.client.get(
            "/api/suppliers/", params={"company_id": cid, "active_only": active_only}
        )
        response.raise_for_status()
        return response.json()

    async def get_supplier(self, supplier_id: int) -> dict[str, Any]:
        """Get supplier by ID"""
        response = await self.client.get(f"/api/suppliers/{supplier_id}")
        response.raise_for_status()
        return response.json()

    async def create_supplier(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new supplier"""
        response = await self.client.post("/api/suppliers/", json=data)
        response.raise_for_status()
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
        params = {"company_id": cid, "active_only": active_only}
        if account_type:
            params["account_type"] = account_type
        response = await self.client.get("/api/accounts/", params=params)
        response.raise_for_status()
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
        response = await self.client.get(f"/api/accounts/{account_id}")
        response.raise_for_status()
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
        params = {"company_id": cid}
        if supplier_id:
            params["supplier_id"] = supplier_id
        if status:
            params["status"] = status
        response = await self.client.get("/api/supplier-invoices/", params=params)
        response.raise_for_status()
        return response.json()

    async def get_supplier_invoice(self, invoice_id: int) -> dict[str, Any]:
        """Get supplier invoice by ID"""
        response = await self.client.get(f"/api/supplier-invoices/{invoice_id}")
        response.raise_for_status()
        return response.json()

    async def create_supplier_invoice(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a supplier invoice"""
        response = await self.client.post("/api/supplier-invoices/", json=data)
        response.raise_for_status()
        return response.json()

    async def register_invoice(self, invoice_id: int) -> dict[str, Any]:
        """Register (book) a supplier invoice"""
        response = await self.client.post(f"/api/supplier-invoices/{invoice_id}/register")
        response.raise_for_status()
        return response.json()

    async def mark_invoice_paid(
        self, invoice_id: int, paid_date: str, paid_amount: Optional[float] = None
    ) -> dict[str, Any]:
        """Mark invoice as paid"""
        data = {"paid_date": paid_date}
        if paid_amount:
            data["paid_amount"] = paid_amount
        response = await self.client.post(
            f"/api/supplier-invoices/{invoice_id}/mark-paid", json=data
        )
        response.raise_for_status()
        return response.json()

    # Default Accounts
    async def list_default_accounts(
        self, company_id: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """List default accounts"""
        cid = company_id or self.company_id
        response = await self.client.get(
            "/api/default-accounts/", params={"company_id": cid}
        )
        response.raise_for_status()
        return response.json()
