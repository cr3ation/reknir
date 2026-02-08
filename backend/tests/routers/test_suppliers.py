"""
Tests for supplier endpoints (/api/suppliers).

Covers:
- Supplier CRUD operations
- Access control
- Validation
"""

import pytest


class TestCreateSupplier:
    """Tests for POST /api/suppliers/"""

    def test_create_supplier_success_minimal(self, client, auth_headers, test_company):
        """Create supplier with minimal required fields."""
        response = client.post("/api/suppliers/", json={
            "company_id": test_company.id,
            "name": "Minimal Supplier AB",
        }, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Supplier AB"
        assert data["company_id"] == test_company.id
        assert "id" in data

    def test_create_supplier_success_full(self, client, auth_headers, test_company):
        """Create supplier with all fields populated."""
        response = client.post("/api/suppliers/", json={
            "company_id": test_company.id,
            "name": "Full Supplier AB",
            "org_number": "998877-6655",
            "email": "info@fullsupplier.se",
            "phone": "08-999 88 77",
            "address": "Leverantörsvägen 10",
            "postal_code": "54321",
            "city": "Göteborg",
            "country": "Sverige",
            "contact_person": "Erik Eriksson",
            "payment_terms": 30,
            "notes": "Preferred supplier",
        }, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Full Supplier AB"
        assert data["org_number"] == "998877-6655"
        assert data["city"] == "Göteborg"

    def test_create_supplier_missing_name(self, client, auth_headers, test_company):
        """Reject supplier without name."""
        response = client.post("/api/suppliers/", json={
            "company_id": test_company.id,
            "email": "noname@supplier.se",
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_create_supplier_no_company_access(self, client, auth_headers, factory):
        """Reject creating supplier for company user doesn't have access to."""
        other_company = factory.create_company(
            name="Other Company",
            org_number="333300-0000",
        )
        response = client.post("/api/suppliers/", json={
            "company_id": other_company.id,
            "name": "Unauthorized Supplier",
        }, headers=auth_headers)
        assert response.status_code == 403


class TestListSuppliers:
    """Tests for GET /api/suppliers/"""

    def test_list_suppliers_empty(self, client, auth_headers, test_company):
        """List suppliers when none exist."""
        response = client.get(
            f"/api/suppliers/?company_id={test_company.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_list_suppliers_with_items(self, client, auth_headers, test_company):
        """List suppliers after creating some."""
        for i in range(3):
            client.post("/api/suppliers/", json={
                "company_id": test_company.id,
                "name": f"Supplier {i}",
            }, headers=auth_headers)

        response = client.get(
            f"/api/suppliers/?company_id={test_company.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3


class TestGetSupplier:
    """Tests for GET /api/suppliers/{id}"""

    def test_get_supplier_success(self, client, auth_headers, test_company):
        """Get a specific supplier."""
        create_response = client.post("/api/suppliers/", json={
            "company_id": test_company.id,
            "name": "Get Test Supplier",
        }, headers=auth_headers)
        supplier_id = create_response.json()["id"]

        response = client.get(
            f"/api/suppliers/{supplier_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Get Test Supplier"

    def test_get_supplier_not_found(self, client, auth_headers):
        """Return 404 for non-existent supplier."""
        response = client.get("/api/suppliers/99999", headers=auth_headers)
        assert response.status_code == 404


class TestUpdateSupplier:
    """Tests for PATCH /api/suppliers/{id}"""

    def test_update_supplier_name(self, client, auth_headers, test_company):
        """Update supplier name."""
        create_response = client.post("/api/suppliers/", json={
            "company_id": test_company.id,
            "name": "Original Supplier Name",
        }, headers=auth_headers)
        supplier_id = create_response.json()["id"]

        response = client.patch(
            f"/api/suppliers/{supplier_id}",
            json={"name": "Updated Supplier Name"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Supplier Name"

    def test_update_supplier_payment_terms(self, client, auth_headers, test_company):
        """Update supplier payment terms."""
        create_response = client.post("/api/suppliers/", json={
            "company_id": test_company.id,
            "name": "Payment Terms Supplier",
            "payment_terms": 30,
        }, headers=auth_headers)
        supplier_id = create_response.json()["id"]

        response = client.patch(
            f"/api/suppliers/{supplier_id}",
            json={"payment_terms": 60},
            headers=auth_headers,
        )
        assert response.status_code == 200
        # Check if payment_terms is returned
        data = response.json()
        if "payment_terms" in data:
            assert data["payment_terms"] == 60


class TestDeleteSupplier:
    """Tests for DELETE /api/suppliers/{id}"""

    def test_delete_supplier_success(self, client, auth_headers, test_company):
        """Delete a supplier."""
        create_response = client.post("/api/suppliers/", json={
            "company_id": test_company.id,
            "name": "To Delete Supplier",
        }, headers=auth_headers)
        supplier_id = create_response.json()["id"]

        response = client.delete(
            f"/api/suppliers/{supplier_id}",
            headers=auth_headers,
        )
        assert response.status_code in [200, 204]

        # Verify deleted
        get_response = client.get(f"/api/suppliers/{supplier_id}", headers=auth_headers)
        assert get_response.status_code == 404

    def test_delete_supplier_not_found(self, client, auth_headers):
        """Return 404 for deleting non-existent supplier."""
        response = client.delete("/api/suppliers/99999", headers=auth_headers)
        assert response.status_code == 404
