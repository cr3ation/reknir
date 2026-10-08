"""Behandlingshistorik: read access to the audit log."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user, verify_company_access
from app.models.compliance import AuditLog
from app.models.user import User
from app.schemas.compliance import AuditLogEntry

router = APIRouter()


@router.get("/", response_model=list[AuditLogEntry])
async def list_audit_log(
    company_id: int | None = Query(None),
    table_name: str | None = Query(None),
    record_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Entries newest first. Company members see their company; instance-wide needs admin."""
    if company_id is not None:
        await verify_company_access(company_id, current_user, db)
    elif not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required for instance-wide history")
    query = db.query(AuditLog)
    if company_id is not None:
        query = query.filter(AuditLog.company_id == company_id)
    if table_name:
        query = query.filter(AuditLog.table_name == table_name)
    if record_id is not None:
        query = query.filter(AuditLog.record_id == record_id)
    rows = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit).all()
    return [
        AuditLogEntry(
            id=r.id,
            company_id=r.company_id,
            user_email=r.user_email,
            action=r.action,
            table_name=r.table_name,
            record_id=r.record_id,
            summary=r.summary,
            changes=json.loads(r.changes) if r.changes else None,
            created_at=r.created_at,
        )
        for r in rows
    ]
