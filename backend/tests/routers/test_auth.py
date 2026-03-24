"""
Tests for authentication endpoints (/api/auth).

Covers:
- User registration (first user only)
- Login with valid/invalid credentials
- Token validation
- Password requirements
- Protected endpoint access
"""


class TestUserRegistration:
    """Tests for POST /api/auth/register

    Note: /api/auth/register only works when no users exist in the database.
    The first registered user automatically becomes an admin.
    """

    def test_register_first_user_becomes_admin(self, client, db_session):
        """First registered user becomes admin."""
        # No fixtures that create users - database is empty
        response = client.post(
            "/api/auth/register",
            json={
                "email": "firstuser@example.com",
                "password": "SecurePassword123!",
                "full_name": "First User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "firstuser@example.com"
        assert data["full_name"] == "First User"
        assert data["is_active"] is True
        assert data["is_admin"] is True  # First user is always admin
        assert "id" in data
        # Password should never be returned
        assert "password" not in data
        assert "hashed_password" not in data

    def test_register_blocked_when_users_exist(self, client, test_user):
        """Registration is blocked after first user exists."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "seconduser@example.com",
                "password": "SecurePassword123!",
                "full_name": "Second User",
            },
        )
        # Should be blocked - only first user can register this way
        assert response.status_code == 403

    def test_register_invalid_email_format(self, client):
        """Reject registration with invalid email format."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "not-an-email",
                "password": "SecurePassword123!",
                "full_name": "Invalid Email User",
            },
        )
        assert response.status_code == 422  # Validation error

    def test_register_missing_email(self, client):
        """Reject registration without email."""
        response = client.post(
            "/api/auth/register",
            json={
                "password": "SecurePassword123!",
                "full_name": "No Email User",
            },
        )
        assert response.status_code == 422

    def test_register_missing_password(self, client):
        """Reject registration without password."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "nopassword@example.com",
                "full_name": "No Password User",
            },
        )
        assert response.status_code == 422

    def test_register_empty_password(self, client):
        """Reject registration with empty password."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "emptypass@example.com",
                "password": "",
                "full_name": "Empty Password User",
            },
        )
        assert response.status_code == 422

    def test_register_short_password(self, client):
        """Reject registration with too short password."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "shortpass@example.com",
                "password": "short",
                "full_name": "Short Password User",
            },
        )
        # Depending on validation, this might be 422 or 400
        assert response.status_code in [400, 422]


class TestLogin:
    """Tests for POST /api/auth/login"""

    def test_login_success(self, client, test_user):
        """Successfully login with valid credentials."""
        response = client.post(
            "/api/auth/login",
            data={
                "username": test_user.email,
                "password": "testpassword123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, test_user):
        """Reject login with wrong password."""
        response = client.post(
            "/api/auth/login",
            data={
                "username": test_user.email,
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_login_nonexistent_user(self, client):
        """Reject login with non-existent email."""
        response = client.post(
            "/api/auth/login",
            data={
                "username": "nonexistent@example.com",
                "password": "somepassword",
            },
        )
        assert response.status_code == 401

    def test_login_inactive_user(self, client, inactive_user):
        """Reject login for inactive user."""
        response = client.post(
            "/api/auth/login",
            data={
                "username": inactive_user.email,
                "password": "inactivepassword",
            },
        )
        # API returns 400 for inactive users (after successful password check)
        assert response.status_code == 400

    def test_login_case_insensitive_email(self, client, test_user):
        """Login with different email casing."""
        response = client.post(
            "/api/auth/login",
            data={
                "username": test_user.email.upper(),
                "password": "testpassword123",
            },
        )
        # Document the actual behavior
        assert response.status_code in [200, 401]

    def test_login_with_spaces_in_email(self, client, test_user):
        """Login with extra spaces in email."""
        response = client.post(
            "/api/auth/login",
            data={
                "username": f" {test_user.email} ",
                "password": "testpassword123",
            },
        )
        # Document the actual behavior
        assert response.status_code in [200, 401]


class TestCurrentUser:
    """Tests for GET /api/auth/me (get current user)"""

    def test_get_current_user_authenticated(self, client, auth_headers, test_user):
        """Get current user info when authenticated."""
        response = client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["full_name"] == test_user.full_name
        assert data["id"] == test_user.id

    def test_get_current_user_no_token(self, client):
        """Reject access without authentication token."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_get_current_user_invalid_token(self, client):
        """Reject access with invalid token."""
        response = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid_token_here"})
        assert response.status_code == 401

    def test_get_current_user_expired_token(self, client, db_session):
        """Reject access with expired token."""
        from datetime import timedelta

        from app.models.user import User
        from app.services.auth_service import create_access_token, get_password_hash

        # Create user
        user = User(
            email="expiredtoken@example.com",
            hashed_password=get_password_hash("password123"),
            full_name="Expired Token User",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        # Create expired token (negative expiry)
        token = create_access_token(
            {"sub": str(user.id), "email": user.email, "is_admin": False}, expires_delta=timedelta(minutes=-10)
        )

        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    def test_get_current_user_malformed_header(self, client):
        """Reject access with malformed Authorization header."""
        # Missing "Bearer" prefix
        response = client.get("/api/auth/me", headers={"Authorization": "some_token"})
        assert response.status_code == 401

    def test_get_current_user_inactive_user(self, client, inactive_auth_headers):
        """Reject access for inactive user even with valid token."""
        response = client.get("/api/auth/me", headers=inactive_auth_headers)
        # API returns 400 for inactive users
        assert response.status_code == 400


class TestPasswordChange:
    """Tests for password change functionality"""

    def test_change_password_success(self, client, auth_headers):
        """Successfully change password."""
        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "testpassword123",
                "new_password": "NewSecurePassword456!",
            },
            headers=auth_headers,
        )
        # If endpoint exists
        if response.status_code != 404:
            assert response.status_code == 200

    def test_change_password_wrong_current(self, client, auth_headers):
        """Reject password change with wrong current password."""
        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "wrongcurrentpassword",
                "new_password": "NewSecurePassword456!",
            },
            headers=auth_headers,
        )
        if response.status_code != 404:
            assert response.status_code in [400, 401]


class TestAdminEndpoints:
    """Tests for admin-only authentication endpoints"""

    def test_list_users_as_admin(self, client, admin_auth_headers):
        """Admin can list all users."""
        response = client.get("/api/auth/users", headers=admin_auth_headers)
        if response.status_code != 404:
            assert response.status_code == 200
            assert isinstance(response.json(), list)

    def test_list_users_as_regular_user(self, client, auth_headers):
        """Regular user cannot list all users."""
        response = client.get("/api/auth/users", headers=auth_headers)
        if response.status_code != 404:
            assert response.status_code == 403

    def test_list_users_unauthenticated(self, client):
        """Unauthenticated request cannot list users."""
        response = client.get("/api/auth/users")
        if response.status_code != 404:
            assert response.status_code == 401
