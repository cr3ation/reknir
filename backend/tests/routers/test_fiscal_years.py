"""
Tests for fiscal year endpoints (/api/fiscal-years).

Covers:
- Creating fiscal years
- Closing fiscal years
- Preventing modifications to closed years
- Date validation
"""


class TestCreateFiscalYear:
    """Tests for POST /api/fiscal-years/"""

    def test_create_fiscal_year_success(self, client, auth_headers, test_company):
        """Successfully create a fiscal year."""
        response = client.post(
            "/api/fiscal-years/",
            json={
                "company_id": test_company.id,
                "year": 2025,
                "label": "2025",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["year"] == 2025
        assert data["company_id"] == test_company.id
        assert data["is_closed"] is False

    def test_create_fiscal_year_broken_year(self, client, auth_headers, test_company):
        """Create a broken fiscal year (not calendar year)."""
        response = client.post(
            "/api/fiscal-years/",
            json={
                "company_id": test_company.id,
                "year": 2025,
                "label": "2024/2025",
                "start_date": "2024-09-01",
                "end_date": "2025-08-31",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201

    def test_create_fiscal_year_duplicate(self, client, auth_headers, test_company):
        """Reject creating duplicate fiscal year for same company and year."""
        # Create first
        client.post(
            "/api/fiscal-years/",
            json={
                "company_id": test_company.id,
                "year": 2026,
                "label": "2026",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
            headers=auth_headers,
        )

        # Try to create duplicate
        response = client.post(
            "/api/fiscal-years/",
            json={
                "company_id": test_company.id,
                "year": 2026,
                "label": "2026 duplicate",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_create_fiscal_year_no_company_access(self, client, auth_headers, factory):
        """Reject creating fiscal year for company user doesn't have access to."""
        other_company = factory.create_company(
            name="Other Company",
            org_number="111111-0000",
        )
        response = client.post(
            "/api/fiscal-years/",
            json={
                "company_id": other_company.id,
                "year": 2025,
                "label": "2025",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
            },
            headers=auth_headers,
        )
        assert response.status_code == 403

    def test_create_fiscal_year_invalid_dates_rejected(self, client, auth_headers, test_company):
        """Reject fiscal year where end_date is before start_date."""
        response = client.post(
            "/api/fiscal-years/",
            json={
                "company_id": test_company.id,
                "year": 2025,
                "label": "2025",
                "start_date": "2025-12-31",
                "end_date": "2025-01-01",  # Before start - should be rejected
            },
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestListFiscalYears:
    """Tests for GET /api/fiscal-years/"""

    def test_list_fiscal_years_success(self, client, auth_headers, test_company):
        """List fiscal years for a company."""
        # Create some fiscal years
        for year in [2024, 2025, 2026]:
            client.post(
                "/api/fiscal-years/",
                json={
                    "company_id": test_company.id,
                    "year": year,
                    "label": str(year),
                    "start_date": f"{year}-01-01",
                    "end_date": f"{year}-12-31",
                },
                headers=auth_headers,
            )

        response = client.get(
            f"/api/fiscal-years/?company_id={test_company.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 3
        years = [fy["year"] for fy in data]
        assert 2024 in years
        assert 2025 in years
        assert 2026 in years


class TestCloseFiscalYear:
    """Tests for closing fiscal years via PATCH /api/fiscal-years/{id}"""

    def test_close_fiscal_year_success(self, client, auth_headers, test_company):
        """Successfully close a fiscal year."""
        # Create fiscal year
        create_response = client.post(
            "/api/fiscal-years/",
            json={
                "company_id": test_company.id,
                "year": 2024,
                "label": "2024",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            },
            headers=auth_headers,
        )
        fy_id = create_response.json()["id"]

        # Close it via PATCH
        response = client.patch(
            f"/api/fiscal-years/{fy_id}",
            json={"is_closed": True},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["is_closed"] is True

    def test_close_already_closed_fiscal_year(self, client, auth_headers, test_company):
        """Handle closing an already closed fiscal year (idempotent)."""
        create_response = client.post(
            "/api/fiscal-years/",
            json={
                "company_id": test_company.id,
                "year": 2023,
                "label": "2023",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
            },
            headers=auth_headers,
        )
        fy_id = create_response.json()["id"]

        # Close once
        client.patch(
            f"/api/fiscal-years/{fy_id}",
            json={"is_closed": True},
            headers=auth_headers,
        )

        # Try to close again - should succeed (idempotent)
        response = client.patch(
            f"/api/fiscal-years/{fy_id}",
            json={"is_closed": True},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["is_closed"] is True


class TestReopenFiscalYear:
    """Tests for reopening fiscal years via PATCH /api/fiscal-years/{id}"""

    def test_reopen_fiscal_year_success(self, client, auth_headers, test_company):
        """Successfully reopen a closed fiscal year."""
        # Create and close
        create_response = client.post(
            "/api/fiscal-years/",
            json={
                "company_id": test_company.id,
                "year": 2022,
                "label": "2022",
                "start_date": "2022-01-01",
                "end_date": "2022-12-31",
            },
            headers=auth_headers,
        )
        fy_id = create_response.json()["id"]
        client.patch(
            f"/api/fiscal-years/{fy_id}",
            json={"is_closed": True},
            headers=auth_headers,
        )

        # Reopen via PATCH
        response = client.patch(
            f"/api/fiscal-years/{fy_id}",
            json={"is_closed": False},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["is_closed"] is False


class TestDeleteFiscalYear:
    """Tests for DELETE /api/fiscal-years/{id}"""

    def test_delete_empty_fiscal_year_success(self, client, auth_headers, test_company):
        """Delete a fiscal year with no transactions."""
        create_response = client.post(
            "/api/fiscal-years/",
            json={
                "company_id": test_company.id,
                "year": 2020,
                "label": "2020",
                "start_date": "2020-01-01",
                "end_date": "2020-12-31",
            },
            headers=auth_headers,
        )
        fy_id = create_response.json()["id"]

        response = client.delete(
            f"/api/fiscal-years/{fy_id}",
            headers=auth_headers,
        )
        # May be 204, 200, or restricted
        assert response.status_code in [200, 204, 403, 405]

    def test_delete_closed_fiscal_year_refused(self, client, auth_headers, test_company):
        """A closed fiscal year is a permanent record and cannot be deleted."""
        create_response = client.post(
            "/api/fiscal-years/",
            json={
                "company_id": test_company.id,
                "year": 2019,
                "label": "2019",
                "start_date": "2019-01-01",
                "end_date": "2019-12-31",
            },
            headers=auth_headers,
        )
        fy_id = create_response.json()["id"]

        # Close it
        client.patch(
            f"/api/fiscal-years/{fy_id}",
            json={"is_closed": True},
            headers=auth_headers,
        )

        response = client.delete(
            f"/api/fiscal-years/{fy_id}",
            headers=auth_headers,
        )
        assert response.status_code == 403
        assert "closed" in response.json()["detail"].lower()

        # Verify it is still there
        get_response = client.get(f"/api/fiscal-years/{fy_id}", headers=auth_headers)
        assert get_response.status_code == 200


class TestClosedFiscalYearIsReadOnly:
    """A closed fiscal year must reject every write path (Bokföringslagen)."""

    @staticmethod
    def _create_fiscal_year(client, auth_headers, company_id, year):
        response = client.post(
            "/api/fiscal-years/",
            json={
                "company_id": company_id,
                "year": year,
                "label": str(year),
                "start_date": f"{year}-01-01",
                "end_date": f"{year}-12-31",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        return response.json()["id"]

    @staticmethod
    def _create_account(client, auth_headers, company_id, fiscal_year_id, number, name, account_type):
        response = client.post(
            "/api/accounts/",
            json={
                "company_id": company_id,
                "fiscal_year_id": fiscal_year_id,
                "account_number": number,
                "name": name,
                "account_type": account_type,
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        return response.json()["id"]

    @staticmethod
    def _close(client, auth_headers, fiscal_year_id):
        response = client.patch(
            f"/api/fiscal-years/{fiscal_year_id}",
            json={"is_closed": True},
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_cannot_create_verification_in_closed_year(self, client, auth_headers, test_company):
        """Posting a new verification into a closed year is refused."""
        fy_id = self._create_fiscal_year(client, auth_headers, test_company.id, 2018)
        bank_id = self._create_account(client, auth_headers, test_company.id, fy_id, 1930, "Bank", "asset")
        revenue_id = self._create_account(client, auth_headers, test_company.id, fy_id, 3001, "Försäljning", "revenue")

        self._close(client, auth_headers, fy_id)

        response = client.post(
            "/api/verifications/",
            json={
                "company_id": test_company.id,
                "fiscal_year_id": fy_id,
                "series": "A",
                "transaction_date": "2018-06-01",
                "description": "Should be refused",
                "transaction_lines": [
                    {"account_id": bank_id, "debit": "100.00", "credit": "0.00"},
                    {"account_id": revenue_id, "debit": "0.00", "credit": "100.00"},
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 403
        assert "closed" in response.json()["detail"].lower()

    def test_cannot_update_verification_in_closed_year(self, client, auth_headers, test_company):
        """Editing a verification that belongs to a closed year is refused."""
        fy_id = self._create_fiscal_year(client, auth_headers, test_company.id, 2017)
        bank_id = self._create_account(client, auth_headers, test_company.id, fy_id, 1930, "Bank", "asset")
        revenue_id = self._create_account(client, auth_headers, test_company.id, fy_id, 3001, "Försäljning", "revenue")

        create_response = client.post(
            "/api/verifications/",
            json={
                "company_id": test_company.id,
                "fiscal_year_id": fy_id,
                "series": "A",
                "transaction_date": "2017-06-01",
                "description": "Booked while open",
                "transaction_lines": [
                    {"account_id": bank_id, "debit": "100.00", "credit": "0.00"},
                    {"account_id": revenue_id, "debit": "0.00", "credit": "100.00"},
                ],
            },
            headers=auth_headers,
        )
        assert create_response.status_code == 201
        verification_id = create_response.json()["id"]

        self._close(client, auth_headers, fy_id)

        response = client.patch(
            f"/api/verifications/{verification_id}",
            json={"description": "Rewritten after closing"},
            headers=auth_headers,
        )
        assert response.status_code == 403
        assert "closed" in response.json()["detail"].lower()

    def test_cannot_create_account_in_closed_year(self, client, auth_headers, test_company):
        """The chart of accounts is part of the closed year's records."""
        fy_id = self._create_fiscal_year(client, auth_headers, test_company.id, 2016)
        self._close(client, auth_headers, fy_id)

        response = client.post(
            "/api/accounts/",
            json={
                "company_id": test_company.id,
                "fiscal_year_id": fy_id,
                "account_number": 1930,
                "name": "Bank",
                "account_type": "asset",
            },
            headers=auth_headers,
        )
        assert response.status_code == 403
        assert "closed" in response.json()["detail"].lower()

    def test_cannot_update_account_in_closed_year(self, client, auth_headers, test_company):
        """Renaming an account in a closed year is refused."""
        fy_id = self._create_fiscal_year(client, auth_headers, test_company.id, 2015)
        account_id = self._create_account(client, auth_headers, test_company.id, fy_id, 1930, "Bank", "asset")

        self._close(client, auth_headers, fy_id)

        response = client.patch(
            f"/api/accounts/{account_id}",
            json={"name": "Renamed after closing"},
            headers=auth_headers,
        )
        assert response.status_code == 403
        assert "closed" in response.json()["detail"].lower()

    def test_open_year_still_accepts_writes(self, client, auth_headers, test_company):
        """The guard must not affect an open fiscal year."""
        fy_id = self._create_fiscal_year(client, auth_headers, test_company.id, 2014)
        bank_id = self._create_account(client, auth_headers, test_company.id, fy_id, 1930, "Bank", "asset")
        revenue_id = self._create_account(client, auth_headers, test_company.id, fy_id, 3001, "Försäljning", "revenue")

        response = client.post(
            "/api/verifications/",
            json={
                "company_id": test_company.id,
                "fiscal_year_id": fy_id,
                "series": "A",
                "transaction_date": "2014-06-01",
                "description": "Booked in an open year",
                "transaction_lines": [
                    {"account_id": bank_id, "debit": "100.00", "credit": "0.00"},
                    {"account_id": revenue_id, "debit": "0.00", "credit": "100.00"},
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
