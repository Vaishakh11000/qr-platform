from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog


def list_audit_logs(
    db: Session,
    *,
    offset: int = 0,
    limit: int = 50,
    admin_id: UUID | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> tuple[list[AuditLog], int]:
    filters = []

    if admin_id is not None:
        filters.append(AuditLog.admin_id == admin_id)

    if action is not None:
        filters.append(AuditLog.action == action)

    if entity_type is not None:
        filters.append(AuditLog.entity_type == entity_type)

    if entity_id is not None:
        filters.append(AuditLog.entity_id == entity_id)

    if created_from is not None:
        filters.append(AuditLog.created_at >= created_from)

    if created_to is not None:
        filters.append(AuditLog.created_at <= created_to)

    count_query = select(func.count()).select_from(AuditLog)

    query = select(AuditLog)

    if filters:
        count_query = count_query.where(*filters)
        query = query.where(*filters)

    total = db.scalar(count_query) or 0

    query = (
        query
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
    )

    records = list(db.scalars(query).all())

    return records, total


def get_audit_log(
    db: Session,
    audit_log_id: UUID,
) -> AuditLog | None:
    return db.get(AuditLog, audit_log_id)
