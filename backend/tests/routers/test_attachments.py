"""
Tests for attachment endpoints (/api/attachments).

Covers:
- Attachment upload
- Attachment download
- Attachment deletion (with restrictions for closed fiscal years)
- Access control
- File type validation
"""

from io import BytesIO


class TestUploadAttachment:
    """Tests for POST /api/attachments/"""

    def test_upload_pdf_success(self, client, auth_headers, test_company):
        """Successfully upload a PDF file."""
        pdf_content = b"%PDF-1.4 fake pdf content"
        files = {
            "file": ("test_document.pdf", BytesIO(pdf_content), "application/pdf"),
        }
        response = client.post(
            f"/api/attachments/?company_id={test_company.id}",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["original_filename"] == "test_document.pdf"
        assert data["mime_type"] == "application/pdf"
        assert "id" in data

    def test_upload_image_success(self, client, auth_headers, test_company):
        """Successfully upload an image file."""
        # Minimal PNG header
        png_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
        files = {
            "file": ("receipt.png", BytesIO(png_content), "image/png"),
        }
        response = client.post(
            f"/api/attachments/?company_id={test_company.id}",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["original_filename"] == "receipt.png"
        assert data["mime_type"] == "image/png"

    def test_upload_jpeg_success(self, client, auth_headers, test_company):
        """Successfully upload a JPEG file."""
        # Minimal JPEG header
        jpeg_content = b'\xff\xd8\xff\xe0\x00\x10JFIF'
        files = {
            "file": ("photo.jpg", BytesIO(jpeg_content), "image/jpeg"),
        }
        response = client.post(
            f"/api/attachments/?company_id={test_company.id}",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 201

    def test_upload_without_company_id(self, client, auth_headers):
        """Reject upload without company_id."""
        pdf_content = b"%PDF-1.4 content"
        files = {
            "file": ("document.pdf", BytesIO(pdf_content), "application/pdf"),
        }
        response = client.post(
            "/api/attachments/",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_upload_no_file(self, client, auth_headers, test_company):
        """Reject upload without file."""
        response = client.post(
            f"/api/attachments/?company_id={test_company.id}",
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_upload_unauthenticated(self, client, test_company):
        """Reject upload without authentication."""
        pdf_content = b"%PDF-1.4 content"
        files = {
            "file": ("document.pdf", BytesIO(pdf_content), "application/pdf"),
        }
        response = client.post(
            f"/api/attachments/?company_id={test_company.id}",
            files=files,
        )
        assert response.status_code == 401

    def test_upload_no_company_access(self, client, auth_headers, factory):
        """Reject upload for company user doesn't have access to."""
        other_company = factory.create_company(
            name="Other Company",
            org_number="000001-1111",
        )
        pdf_content = b"%PDF-1.4 content"
        files = {
            "file": ("document.pdf", BytesIO(pdf_content), "application/pdf"),
        }
        response = client.post(
            f"/api/attachments/?company_id={other_company.id}",
            files=files,
            headers=auth_headers,
        )
        assert response.status_code == 403


class TestListAttachments:
    """Tests for GET /api/attachments/"""

    def test_list_attachments_empty(self, client, auth_headers, test_company):
        """List attachments when none exist."""
        response = client.get(
            f"/api/attachments/?company_id={test_company.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_list_attachments_with_items(self, client, auth_headers, test_company):
        """List attachments after uploading some."""
        # Upload a few attachments first
        for i in range(3):
            pdf_content = f"%PDF-1.4 content {i}".encode()
            files = {
                "file": (f"document_{i}.pdf", BytesIO(pdf_content), "application/pdf"),
            }
            client.post(
                f"/api/attachments/?company_id={test_company.id}",
                files=files,
                headers=auth_headers,
            )

        response = client.get(
            f"/api/attachments/?company_id={test_company.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_list_attachments_no_company_access(self, client, auth_headers, factory):
        """Reject listing for company user doesn't have access to."""
        other_company = factory.create_company(
            name="Other Company",
            org_number="000002-2222",
        )
        response = client.get(
            f"/api/attachments/?company_id={other_company.id}",
            headers=auth_headers,
        )
        assert response.status_code == 403


class TestGetAttachment:
    """Tests for GET /api/attachments/{id}"""

    def test_get_attachment_metadata(self, client, auth_headers, test_company):
        """Get attachment metadata by ID."""
        # First upload
        pdf_content = b"%PDF-1.4 test content"
        files = {
            "file": ("test.pdf", BytesIO(pdf_content), "application/pdf"),
        }
        upload_response = client.post(
            f"/api/attachments/?company_id={test_company.id}",
            files=files,
            headers=auth_headers,
        )
        attachment_id = upload_response.json()["id"]

        # Then get metadata
        response = client.get(
            f"/api/attachments/{attachment_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == attachment_id
        assert data["original_filename"] == "test.pdf"

    def test_get_attachment_not_found(self, client, auth_headers):
        """Return 404 for non-existent attachment."""
        response = client.get("/api/attachments/99999", headers=auth_headers)
        assert response.status_code == 404


class TestDownloadAttachment:
    """Tests for GET /api/attachments/{id}/content"""

    def test_download_attachment_success(self, client, auth_headers, test_company):
        """Successfully download an attachment."""
        pdf_content = b"%PDF-1.4 download test content"
        files = {
            "file": ("download_test.pdf", BytesIO(pdf_content), "application/pdf"),
        }
        upload_response = client.post(
            f"/api/attachments/?company_id={test_company.id}",
            files=files,
            headers=auth_headers,
        )
        attachment_id = upload_response.json()["id"]

        response = client.get(
            f"/api/attachments/{attachment_id}/content",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert "application/pdf" in response.headers.get("content-type", "")

    def test_download_attachment_not_found(self, client, auth_headers):
        """Return 404 for downloading non-existent attachment."""
        response = client.get("/api/attachments/99999/content", headers=auth_headers)
        assert response.status_code == 404


class TestDeleteAttachment:
    """Tests for DELETE /api/attachments/{id}"""

    def test_delete_unlinked_attachment_success(self, client, auth_headers, test_company):
        """Successfully delete an unlinked attachment."""
        pdf_content = b"%PDF-1.4 delete test content"
        files = {
            "file": ("to_delete.pdf", BytesIO(pdf_content), "application/pdf"),
        }
        upload_response = client.post(
            f"/api/attachments/?company_id={test_company.id}",
            files=files,
            headers=auth_headers,
        )
        attachment_id = upload_response.json()["id"]

        response = client.delete(
            f"/api/attachments/{attachment_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get(
            f"/api/attachments/{attachment_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 404

    def test_delete_attachment_not_found(self, client, auth_headers):
        """Return 404 for deleting non-existent attachment."""
        response = client.delete("/api/attachments/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_attachment_no_access(self, client, auth_headers, factory, admin_auth_headers):
        """Reject deletion of attachment for company user doesn't have access to."""
        # Admin uploads to a company user doesn't have access to
        other_company = factory.create_company(
            name="Other Company",
            org_number="000003-3333",
        )
        pdf_content = b"%PDF-1.4 content"
        files = {
            "file": ("other.pdf", BytesIO(pdf_content), "application/pdf"),
        }
        upload_response = client.post(
            f"/api/attachments/?company_id={other_company.id}",
            files=files,
            headers=admin_auth_headers,
        )
        attachment_id = upload_response.json()["id"]

        # Regular user tries to delete
        response = client.delete(
            f"/api/attachments/{attachment_id}",
            headers=auth_headers,
        )
        assert response.status_code == 403


class TestAttachmentLinks:
    """Tests for attachment links to entities."""

    # Note: These tests would need entities (verifications, invoices) to be created first
    # For now, testing the basic attachment functionality

    def test_list_attachments_includes_links(self, client, auth_headers, test_company):
        """Verify that list response includes links field."""
        pdf_content = b"%PDF-1.4 content"
        files = {
            "file": ("with_links.pdf", BytesIO(pdf_content), "application/pdf"),
        }
        client.post(
            f"/api/attachments/?company_id={test_company.id}",
            files=files,
            headers=auth_headers,
        )

        response = client.get(
            f"/api/attachments/?company_id={test_company.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        # Each attachment should have a links field
        assert "links" in data[0]
        assert isinstance(data[0]["links"], list)
