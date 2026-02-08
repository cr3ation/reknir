"""
Test configuration and fixtures for pytest.

This module provides:
- In-memory SQLite database for fast, isolated tests
- Authentication fixtures (test users, JWT tokens)
- Test data factories for creating test entities
- Common test utilities
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.account import Account
from app.models.company import AccountingBasis, Company, PaymentType, VATReportingPeriod
from app.models.customer import Customer, Supplier
from app.models.fiscal_year import FiscalYear
from app.models.user import CompanyUser, User
from app.services.auth_service import create_access_token, get_password_hash

# Use in-memory SQLite for tests (faster, no external dependencies)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database session override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# =============================================================================
# User Fixtures
# =============================================================================

@pytest.fixture
def test_user(db_session) -> User:
    """Create a regular test user."""
    user = User(
        email="testuser@example.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="Test User",
        is_admin=False,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session) -> User:
    """Create an admin test user."""
    user = User(
        email="admin@example.com",
        hashed_password=get_password_hash("adminpassword123"),
        full_name="Admin User",
        is_admin=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_user(db_session) -> User:
    """Create an inactive test user."""
    user = User(
        email="inactive@example.com",
        hashed_password=get_password_hash("inactivepassword"),
        full_name="Inactive User",
        is_admin=False,
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# =============================================================================
# Authentication Fixtures
# =============================================================================

@pytest.fixture
def auth_headers(test_user) -> dict:
    """Get authentication headers for the regular test user."""
    token = create_access_token({
        "sub": str(test_user.id),
        "email": test_user.email,
        "is_admin": test_user.is_admin,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(admin_user) -> dict:
    """Get authentication headers for the admin user."""
    token = create_access_token({
        "sub": str(admin_user.id),
        "email": admin_user.email,
        "is_admin": admin_user.is_admin,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def inactive_auth_headers(inactive_user) -> dict:
    """Get authentication headers for the inactive user."""
    token = create_access_token({
        "sub": str(inactive_user.id),
        "email": inactive_user.email,
        "is_admin": inactive_user.is_admin,
    })
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Company Fixtures
# =============================================================================

@pytest.fixture
def test_company(db_session, test_user) -> Company:
    """Create a test company with the test user having access."""
    company = Company(
        name="Test Company AB",
        org_number="123456-7890",
        address="Testgatan 1",
        postal_code="12345",
        city="Stockholm",
        phone="08-123 45 67",
        email="info@testcompany.se",
        fiscal_year_start=date(2025, 1, 1),
        fiscal_year_end=date(2025, 12, 31),
        accounting_basis=AccountingBasis.ACCRUAL,
        vat_reporting_period=VATReportingPeriod.QUARTERLY,
        is_vat_registered=True,
        payment_type=PaymentType.BANKGIRO,
        bankgiro_number="123-4567",
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)

    # Grant user access to company
    company_user = CompanyUser(user_id=test_user.id, company_id=company.id)
    db_session.add(company_user)
    db_session.commit()

    return company


@pytest.fixture
def test_company_with_fiscal_year(db_session, test_company) -> tuple[Company, FiscalYear]:
    """Create a test company with an active fiscal year."""
    fiscal_year = FiscalYear(
        company_id=test_company.id,
        year=2025,
        label="2025",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        is_closed=False,
    )
    db_session.add(fiscal_year)
    db_session.commit()
    db_session.refresh(fiscal_year)
    return test_company, fiscal_year


# =============================================================================
# Account Fixtures
# =============================================================================

@pytest.fixture
def basic_accounts(db_session, test_company) -> list[Account]:
    """Create basic chart of accounts for testing."""
    accounts_data = [
        # Assets
        (1910, "Kassa", "asset"),
        (1920, "Plusgiro", "asset"),
        (1930, "Bankgiro/Bank", "asset"),
        (1510, "Kundfordringar", "asset"),
        # Liabilities
        (2440, "Leverantörsskulder", "liability"),
        (2610, "Utgående moms 25%", "liability"),
        (2640, "Ingående moms", "asset"),
        # Revenue
        (3000, "Försäljning varor", "revenue"),
        (3010, "Försäljning tjänster", "revenue"),
        # Expenses
        (4000, "Inköp varor", "expense"),
        (5010, "Lokalhyra", "expense"),
        (6100, "Kontorsmaterial", "expense"),
    ]

    accounts = []
    for number, name, account_type in accounts_data:
        account = Account(
            company_id=test_company.id,
            account_number=number,
            name=name,
            account_type=account_type,
            is_active=True,
        )
        db_session.add(account)
        accounts.append(account)

    db_session.commit()
    for account in accounts:
        db_session.refresh(account)

    return accounts


# =============================================================================
# Customer & Supplier Fixtures
# =============================================================================

@pytest.fixture
def test_customer(db_session, test_company) -> Customer:
    """Create a test customer."""
    customer = Customer(
        company_id=test_company.id,
        name="Test Kund AB",
        org_number="987654-3210",
        email="kund@testkund.se",
        address="Kundgatan 10",
        postal_code="11111",
        city="Göteborg",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


@pytest.fixture
def test_supplier(db_session, test_company) -> Supplier:
    """Create a test supplier."""
    supplier = Supplier(
        company_id=test_company.id,
        name="Test Leverantör AB",
        org_number="555555-5555",
        email="leverantor@testlev.se",
        address="Leverantörsgatan 5",
        postal_code="22222",
        city="Malmö",
    )
    db_session.add(supplier)
    db_session.commit()
    db_session.refresh(supplier)
    return supplier


# =============================================================================
# Test Data Factories
# =============================================================================

class TestDataFactory:
    """Factory for creating test data entities."""

    def __init__(self, db_session):
        self.db = db_session

    def create_user(
        self,
        email: str = "user@example.com",
        password: str = "password123",
        full_name: str = "Test User",
        is_admin: bool = False,
        is_active: bool = True,
    ) -> User:
        """Create a user with specified attributes."""
        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            is_admin=is_admin,
            is_active=is_active,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def create_company(
        self,
        name: str = "Factory Company AB",
        org_number: str = "111111-1111",
        user: User | None = None,
        payment_type: PaymentType | None = None,
        **kwargs,
    ) -> Company:
        """Create a company with specified attributes."""
        defaults = {
            "address": "Fabriksgatan 1",
            "postal_code": "33333",
            "city": "Uppsala",
            "fiscal_year_start": date(2025, 1, 1),
            "fiscal_year_end": date(2025, 12, 31),
            "accounting_basis": AccountingBasis.ACCRUAL,
            "vat_reporting_period": VATReportingPeriod.QUARTERLY,
            "is_vat_registered": True,
        }
        defaults.update(kwargs)

        company = Company(name=name, org_number=org_number, payment_type=payment_type, **defaults)
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)

        if user:
            company_user = CompanyUser(user_id=user.id, company_id=company.id)
            self.db.add(company_user)
            self.db.commit()

        return company

    def create_fiscal_year(
        self,
        company: Company,
        year: int = 2025,
        is_closed: bool = False,
    ) -> FiscalYear:
        """Create a fiscal year for a company."""
        fiscal_year = FiscalYear(
            company_id=company.id,
            year=year,
            label=str(year),
            start_date=date(year, 1, 1),
            end_date=date(year, 12, 31),
            is_closed=is_closed,
        )
        self.db.add(fiscal_year)
        self.db.commit()
        self.db.refresh(fiscal_year)
        return fiscal_year

    def create_account(
        self,
        company: Company,
        account_number: int,
        name: str,
        account_type: str = "asset",
    ) -> Account:
        """Create an account for a company."""
        account = Account(
            company_id=company.id,
            account_number=account_number,
            name=name,
            account_type=account_type,
            is_active=True,
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account


@pytest.fixture
def factory(db_session) -> TestDataFactory:
    """Get a test data factory instance."""
    return TestDataFactory(db_session)


# =============================================================================
# Utility Functions
# =============================================================================

def assert_error_response(response, status_code: int, detail_contains: str | None = None):
    """Assert that a response is an error with expected status and optional detail."""
    assert response.status_code == status_code, f"Expected {status_code}, got {response.status_code}: {response.text}"
    if detail_contains:
        data = response.json()
        assert "detail" in data, f"Expected 'detail' in response: {data}"
        assert detail_contains.lower() in data["detail"].lower(), f"Expected '{detail_contains}' in '{data['detail']}'"
