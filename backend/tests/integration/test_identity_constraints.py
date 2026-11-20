from uuid import uuid4

import pytest

from app.models import Role, AdminUser, AuditLog
from sqlalchemy.exc import IntegrityError


def create_test_role(db_session, suffix):
    """Create a role for identity integrity tests."""

    role = Role(
        name=f"TEST-ROLE-{suffix}",
        description="Test role",
    )

    db_session.add(role)
    db_session.flush()

    return role


def create_test_admin(db_session, role, suffix):
    """Create an admin user for identity integrity tests."""

    admin = AdminUser(
        name=f"Test Admin {suffix}",
        email=f"admin-{suffix}@example.test",
        password_hash="test-password-hash",
        role_id=role.id,
    )

    db_session.add(admin)
    db_session.flush()

    return admin


@pytest.mark.integration
def test_role_name_must_be_unique(db_session):
    role = create_test_role(db_session, "DUPLICATE")

    duplicate = Role(
        name=role.name,
        description="Duplicate role",
    )

    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_admin_email_must_be_unique(db_session):
    role = create_test_role(db_session, "DUPLICATE-EMAIL")

    admin = create_test_admin(db_session, role, "DUPLICATE")

    duplicate = AdminUser(
        name="Duplicate Admin",
        email=admin.email,
        password_hash="another-test-hash",
        role_id=role.id,
    )

    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_admin_requires_valid_role(db_session):
    admin = AdminUser(
        name="Admin Without Role",
        email="admin-no-role@example.test",
        password_hash="test-password-hash",
        role_id=None,
    )

    db_session.add(admin)

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_audit_log_can_exist_without_admin(db_session):
    audit_log = AuditLog(
        admin_id=None,
        action="SYSTEM_EVENT",
        entity_type="SYSTEM",
    )

    db_session.add(audit_log)
    db_session.flush()

    assert audit_log.id is not None
    assert audit_log.admin_id is None


@pytest.mark.integration
def test_deleting_admin_preserves_audit_log(db_session):
    role = create_test_role(db_session, "AUDIT-DELETE")

    admin = create_test_admin(db_session, role, "AUDIT-DELETE")

    audit_log = AuditLog(
        admin_id=admin.id,
        action="PRODUCT_UPDATED",
        entity_type="PRODUCT",
        entity_id=uuid4(),
        old_values={"name": "Old Product"},
        new_values={"name": "Updated Product"},
    )

    db_session.add(audit_log)
    db_session.flush()

    audit_log_id = audit_log.id

    db_session.delete(admin)
    db_session.flush()

    db_session.refresh(audit_log)

    assert audit_log.id == audit_log_id
    assert audit_log.admin_id is None
    assert audit_log.action == "PRODUCT_UPDATED"