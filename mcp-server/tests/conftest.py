"""Shared fixtures for MCP server tests"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from src.client import ReknirClient


class RequestRecorder:
    """Records HTTP requests made by the client for assertion."""

    def __init__(self):
        self.requests: list[tuple[str, str, dict]] = []  # (method, url, params/json)

    def make_response(self, data=None, status_code=200):
        """Create a mock httpx.Response."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = status_code
        response.json.return_value = data if data is not None else {}
        response.raise_for_status = MagicMock()
        if status_code >= 400:
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                f"{status_code}", request=MagicMock(), response=response
            )
        return response

    async def mock_get(self, url, **kwargs):
        params = kwargs.get("params", {})
        self.requests.append(("GET", url, params))
        return self.make_response(self._get_response_data(url, params))

    async def mock_post(self, url, **kwargs):
        body = kwargs.get("json", {})
        self.requests.append(("POST", url, body))
        return self.make_response(self._get_response_data(url, body))

    def _get_response_data(self, url, params):
        """Return sensible mock data based on the URL."""
        if "fiscal-years/current" in url:
            return {"id": 1, "start_date": "2026-01-01", "end_date": "2026-12-31", "year": 2026, "is_closed": False}
        if "/api/accounts/" in url and "balances" in url:
            return []
        if "/api/accounts/" in url:
            return []
        if "/api/suppliers/" in url:
            return []
        if "/api/supplier-invoices/" in url:
            return []
        if "/api/verifications/" in url:
            return []
        if url == "/api/companies/":
            return [
                {"id": 1, "name": "Test AB", "org_number": "556677-8899", "city": "Stockholm"},
            ]
        if "/api/companies/" in url:
            return {
                "id": 1, "name": "Test AB", "org_number": "556677-8899",
                "fiscal_year_start": "01-01", "fiscal_year_end": "12-31",
                "accounting_basis": "accrual", "vat_reporting_period": "monthly",
            }
        if "/api/reports/" in url:
            return {"sections": []}
        if "/api/default-accounts/" in url:
            return []
        return {}

    def get_params_for(self, url_fragment: str) -> dict:
        """Get the params sent for a request matching the URL fragment."""
        for method, url, params in self.requests:
            if url_fragment in url and method == "GET":
                return params
        raise AssertionError(f"No GET request found matching '{url_fragment}'. Requests: {self.requests}")

    def clear(self):
        self.requests.clear()


@pytest.fixture
def recorder():
    return RequestRecorder()


@pytest.fixture
def client(recorder):
    """Create a ReknirClient with mocked HTTP transport."""
    c = ReknirClient(base_url="http://test", company_id=1, api_key="")
    c._get = recorder.mock_get
    c._post = recorder.mock_post
    return c
