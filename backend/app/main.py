from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import accounts, verifications, companies, reports

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Modern Swedish bookkeeping system with BAS kontoplan support",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(companies.router, prefix="/api/companies", tags=["companies"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(verifications.router, prefix="/api/verifications", tags=["verifications"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Reknir API",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
