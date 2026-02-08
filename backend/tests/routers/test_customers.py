"""
Tests for customer endpoints (/api/customers).

Covers:
- Customer CRUD operations
- Access control
- Validation
"""

import pytest


class TestCreateCustomer:
    """Tests for POST /api/customers/"""

    def test_create_customer_success_minimal(self, client, auth_headers, test_company):
        """Create customer with minimal required fields."""
        response = client.post("/api/customers/", json={
            "company_id": test_company.id,
            "name": "Minimal Customer AB",
        }, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Customer AB"
        assert data["company_id"] == test_company.id
        assert "id" in data

    def test_create_customer_success_full(self, client, auth_headers, test_company):
        """Create customer with all fields populated."""
        response = client.post("/api/customers/", json={
            "company_id": test_company.id,
            "name": "Full Customer AB",
            "org_number": "556677-8899",
            "email": "info@fullcustomer.se",
            "phone": "08-111 22 33",
            "address": "Kundvägen 1",
            "postal_code": "12345",
            "city": "Stockholm",
            "country": "Sverige",
            "contact_person": "Anna Andersson",
            "notes": "Important customer",
        }, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Full Customer AB"
        assert data["org_number"] == "556677-8899"
        assert data["email"] == "info@fullcustomer.se"
        assert data["city"] == "Stockholm"

    def test_create_customer_missing_name(self, client, auth_headers, test_company):
        """Reject customer without name."""
        response = client.post("/api/customers/", json={
            "company_id": test_company.id,
            "email": "noname@customer.se",
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_create_customer_no_company_access(self, client, auth_headers, factory):
        """Reject creating customer for company user doesn't have access to."""
        other_company = factory.create_company(
            name="Other Company",
            org_number="111100-0000",
        )
        response = client.post("/api/customers/", json={
            "company_id": other_company.id,
            "name": "Unauthorized Customer",
        }, headers=auth_headers)
        assert response.status_code == 403

    def test_create_customer_unauthenticated(self, client, test_company):
        """Reject creating customer without authentication."""
        response = client.post("/api/customers/", json={
            "company_id": test_company.id,
            "name": "Unauthenticated Customer",
        })
        assert response.status_code == 401


class TestListCustomers:
    """Tests for GET /api/customers/"""

    def test_list_customers_empty(self, client, auth_headers, test_company):
        """List customers when none exist."""
        response = client.get(
            f"/api/customers/?company_id={test_company.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_list_customers_with_items(self, client, auth_headers, test_company):
        """List customers after creating some."""
        for i in range(3):
            client.post("/api/customers/", json={
                "company_id": test_company.id,
                "name": f"Customer {i}",
            }, headers=auth_headers)

        response = client.get(
            f"/api/customers/?company_id={test_company.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_list_customers_no_company_access(self, client, auth_headers, factory):
        """Reject listing customers for company user doesn't have access to."""
        other_company = factory.create_company(
            name="Other Company",
            org_number="222200-0000",
        )
        response = client.get(
            f"/api/customers/?company_id={other_company.id}",
            headers=auth_headers,
        )
        assert response.status_code == 403


class TestGetCustomer:
    """Tests for GET /api/customers/{id}"""

    def test_get_customer_success(self, client, auth_headers, test_company):
        """Get a specific customer."""
        create_response = client.post("/api/customers/", json={
            "company_id": test_company.id,
            "name": "Get Test Customer",
        }, headers=auth_headers)
        customer_id = create_response.json()["id"]

        response = client.get(
            f"/api/customers/{customer_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Get Test Customer"

    def test_get_customer_not_found(self, client, auth_headers):
        """Return 404 for non-existent customer."""
        response = client.get("/api/customers/99999", headers=auth_headers)
        assert response.status_code == 404


class TestUpdateCustomer:
    """Tests for PATCH /api/customers/{id}"""

    def test_update_customer_name(self, client, auth_headers, test_company):
        """Update customer name."""
        create_response = client.post("/api/customers/", json={
            "company_id": test_company.id,
            "name": "Original Name",
        }, headers=auth_headers)
        customer_id = create_response.json()["id"]

        response = client.patch(
            f"/api/customers/{customer_id}",
            json={"name": "Updated Name"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    def test_update_customer_contact_info(self, client, auth_headers, test_company):
        """Update customer contact information."""
        create_response = client.post("/api/customers/", json={
            "company_id": test_company.id,
            "name": "Contact Update Customer",
        }, headers=auth_headers)
        customer_id = create_response.json()["id"]

        response = client.patch(
            f"/api/customers/{customer_id}",
            json={
                "email": "newemail@customer.se",
                "phone": "070-123 45 67",
                "address": "New Address 1",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "newemail@customer.se"
        assert data["phone"] == "070-123 45 67"
        assert data["address"] == "New Address 1"


class TestDeleteCustomer:
    """Tests for DELETE /api/customers/{id}"""

    def test_delete_customer_success(self, client, auth_headers, test_company):
        """Delete a customer."""
        create_response = client.post("/api/customers/", json={
            "company_id": test_company.id,
            "name": "To Delete Customer",
        }, headers=auth_headers)
        customer_id = create_response.json()["id"]

        response = client.delete(
            f"/api/customers/{customer_id}",
            headers=auth_headers,
        )
        assert response.status_code in [200, 204]

        # Verify deleted
        get_response = client.get(f"/api/customers/{customer_id}", headers=auth_headers)
        assert get_response.status_code == 404

    def test_delete_customer_not_found(self, client, auth_headers):
        """Return 404 for deleting non-existent customer."""
        response = client.delete("/api/customers/99999", headers=auth_headers)
        assert response.status_code == 404
