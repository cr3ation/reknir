from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import accounts, verifications, companies, reports, customers, suppliers, invoices, supplier_invoices, sie4, default_accounts, fiscal_years

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Modern Swedish bookkeeping system with BAS kontoplan support and invoice management",
    version="0.2.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(companies.router, prefix="/api/companies", tags=["companies"])
app.include_router(fiscal_years.router, prefix="/api/fiscal-years", tags=["fiscal-years"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(verifications.router, prefix="/api/verifications", tags=["verifications"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])

# Invoice management routers
app.include_router(customers.router, prefix="/api/customers", tags=["customers"])
app.include_router(suppliers.router, prefix="/api/suppliers", tags=["suppliers"])
app.include_router(invoices.router, prefix="/api/invoices", tags=["invoices"])
app.include_router(supplier_invoices.router, prefix="/api/supplier-invoices", tags=["supplier-invoices"])

# SIE4 import/export and default accounts
app.include_router(sie4.router)
app.include_router(default_accounts.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Reknir API",
        "version": "0.2.0",
        "features": [
            "Swedish BAS kontoplan",
            "Double-entry bookkeeping",
            "Invoice management (outgoing & incoming)",
            "Automatic verification creation",
            "SIE4 import/export",
            "Configurable default accounts",
            "Reports"
        ],
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
