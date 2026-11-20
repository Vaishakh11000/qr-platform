from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import require_super_admin
from app.core.database import get_db
from app.models import AdminUser
from app.schemas.audit_log import AuditLogPage, AuditLogResponse
from app.services.audit_query_service import (
    get_audit_log,
    list_audit_logs,
)


router = APIRouter(tags=["Audit Logs"])


@router.get(
    "/audit-logs",
    response_model=AuditLogPage,
)
def list_audit_logs_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    admin_id: UUID | None = Query(default=None),
    action: str | None = Query(default=None, min_length=1, max_length=100),
    entity_type: str | None = Query(
        default=None,
        min_length=1,
        max_length=80,
    ),
    entity_id: UUID | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    if (
        created_from is not None
        and created_to is not None
        and created_from > created_to
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="created_from must not be later than created_to.",
        )

    records, total = list_audit_logs(
        db,
        offset=offset,
        limit=limit,
        admin_id=admin_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        created_from=created_from,
        created_to=created_to,
    )

    return {
        "items": records,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get(
    "/audit-logs/{audit_log_id}",
    response_model=AuditLogResponse,
)
def get_audit_log_endpoint(
    audit_log_id: UUID,
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    audit_log = get_audit_log(db, audit_log_id)

    if audit_log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found.",
        )

    return audit_log
