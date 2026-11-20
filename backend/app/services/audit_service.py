from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AuditLog


def record_audit_event(
    db: Session,
    *,
    admin_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    old_values: dict | None = None,
    new_values: dict | None = None,
) -> AuditLog:
    """
    Add an audit record to the current database transaction.

    This function deliberately does not commit. The caller must commit
    the audit record together with the operation being audited.
    """

    audit_log = AuditLog(
        admin_id=admin_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values=old_values,
        new_values=new_values,
    )

    db.add(audit_log)

    return audit_log
