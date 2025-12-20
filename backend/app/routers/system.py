"""
System information router - provides public system status and configuration
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/info")
def get_system_info(db: Session = Depends(get_db)):
    """
    Get system information and status.
    This endpoint is public (no authentication required).

    Returns:
        needs_setup: True if no users exist and initial setup is required
        version: Application version
    """
    user_count = db.query(User).count()

    return {
        "needs_setup": user_count == 0,
        "version": "1.0.0",
    }
