from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.security import create_access_token, hash_password
from app.models import AdminUser, AuditLog, Role


def create_admin(db, role_name="SUPER_ADMIN"):
    role = db.query(Role).filter_by(name=role_name).one_or_none()

    if role is None:
        role = Role(
            name=role_name,
            description="Audit API test role",
        )
        db.add(role)
        db.flush()

    admin = AdminUser(
        name="Audit Test Admin",
        email=f"{uuid4().hex}@example.test",
        password_hash=hash_password("Test-Password-123!"),
        role_id=role.id,
        is_active=True,
    )
    db.add(admin)
    db.flush()

    token = create_access_token(admin.id)
    return {"Authorization": f"Bearer {token}"}, admin


def create_audit_log(
    db,
    *,
    admin_id=None,
    action="TEST_ACTION",
    entity_type="TEST_ENTITY",
    entity_id=None,
    created_at=None,
):
    record = AuditLog(
        admin_id=admin_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id or uuid4(),
        old_values={"status": "before"},
        new_values={"status": "after"},
        ip_hash="test-ip-hash",
    )

    if created_at is not None:
        record.created_at = created_at

    db.add(record)
    db.flush()
    return record


def test_audit_list_requires_authentication(client):
    response = client.get("/api/v1/audit-logs")
    assert response.status_code == 401


def test_audit_detail_requires_authentication(client):
    response = client.get(f"/api/v1/audit-logs/{uuid4()}")
    assert response.status_code == 401


def test_audit_list_rejects_non_super_admin(client, db_session):
    headers, _ = create_admin(db_session, "CONTENT_EDITOR")

    response = client.get(
        "/api/v1/audit-logs",
        headers=headers,
    )

    assert response.status_code == 403


def test_list_audit_logs_returns_paginated_results(client, db_session):
    headers, admin = create_admin(db_session)

    now = datetime.now(timezone.utc)

    first = create_audit_log(
        db_session,
        admin_id=admin.id,
        action="ACTION_ONE",
        created_at=now - timedelta(minutes=2),
    )
    second = create_audit_log(
        db_session,
        admin_id=admin.id,
        action="ACTION_TWO",
        created_at=now - timedelta(minutes=1),
    )
    third = create_audit_log(
        db_session,
        admin_id=admin.id,
        action="ACTION_THREE",
        created_at=now,
    )

    response = client.get(
        "/api/v1/audit-logs",
        params={"offset": 0, "limit": 2},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 3
    assert data["offset"] == 0
    assert data["limit"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["id"] == str(third.id)
    assert data["items"][1]["id"] == str(second.id)

    next_page = client.get(
        "/api/v1/audit-logs",
        params={"offset": 2, "limit": 2},
        headers=headers,
    )

    assert next_page.status_code == 200
    assert len(next_page.json()["items"]) == 1
    assert next_page.json()["items"][0]["id"] == str(first.id)


def test_audit_list_filters_by_admin_action_and_entity(
    client,
    db_session,
):
    headers, admin = create_admin(db_session)
    _, another_admin = create_admin(db_session)

    target_entity_id = uuid4()

    matching = create_audit_log(
        db_session,
        admin_id=admin.id,
        action="PRODUCT_UPDATED",
        entity_type="PRODUCT",
        entity_id=target_entity_id,
    )

    create_audit_log(
        db_session,
        admin_id=another_admin.id,
        action="PRODUCT_UPDATED",
        entity_type="PRODUCT",
        entity_id=target_entity_id,
    )

    create_audit_log(
        db_session,
        admin_id=admin.id,
        action="QR_CREATED",
        entity_type="QR_CODE",
    )

    response = client.get(
        "/api/v1/audit-logs",
        params={
            "admin_id": str(admin.id),
            "action": "PRODUCT_UPDATED",
            "entity_type": "PRODUCT",
            "entity_id": str(target_entity_id),
        },
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == str(matching.id)


def test_audit_list_filters_by_date_range(client, db_session):
    headers, admin = create_admin(db_session)

    now = datetime.now(timezone.utc)

    older = create_audit_log(
        db_session,
        admin_id=admin.id,
        created_at=now - timedelta(days=3),
    )
    included = create_audit_log(
        db_session,
        admin_id=admin.id,
        created_at=now - timedelta(days=1),
    )
    newer = create_audit_log(
        db_session,
        admin_id=admin.id,
        created_at=now,
    )

    response = client.get(
        "/api/v1/audit-logs",
        params={
            "created_from": (now - timedelta(days=2)).isoformat(),
            "created_to": (now - timedelta(hours=12)).isoformat(),
        },
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert data["items"][0]["id"] == str(included.id)
    assert str(older.id) not in {
        item["id"] for item in data["items"]
    }
    assert str(newer.id) not in {
        item["id"] for item in data["items"]
    }


def test_audit_date_filter_includes_final_microsecond_of_day(client, db_session):
    headers, admin = create_admin(db_session)
    start = datetime(2026, 5, 12, tzinfo=timezone.utc)
    end = datetime(2026, 5, 12, 23, 59, 59, 999999, tzinfo=timezone.utc)
    included = create_audit_log(db_session, admin_id=admin.id, created_at=end)
    create_audit_log(
        db_session,
        admin_id=admin.id,
        created_at=end + timedelta(microseconds=1),
    )

    response = client.get(
        "/api/v1/audit-logs",
        params={"created_from": start.isoformat(), "created_to": end.isoformat()},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == str(included.id)


def test_audit_list_rejects_invalid_date_range(client, db_session):
    headers, _ = create_admin(db_session)

    now = datetime.now(timezone.utc)

    response = client.get(
        "/api/v1/audit-logs",
        params={
            "created_from": now.isoformat(),
            "created_to": (now - timedelta(days=1)).isoformat(),
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_get_audit_log_detail(client, db_session):
    headers, admin = create_admin(db_session)

    record = create_audit_log(
        db_session,
        admin_id=admin.id,
        action="PRODUCT_UPDATED",
        entity_type="PRODUCT",
    )

    response = client.get(
        f"/api/v1/audit-logs/{record.id}",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(record.id)
    assert data["admin_id"] == str(admin.id)
    assert data["action"] == "PRODUCT_UPDATED"
    assert data["entity_type"] == "PRODUCT"
    assert data["old_values"] == {"status": "before"}
    assert data["new_values"] == {"status": "after"}
    assert data["ip_hash"] == "test-ip-hash"


def test_get_nonexistent_audit_log(client, db_session):
    headers, _ = create_admin(db_session)

    response = client.get(
        f"/api/v1/audit-logs/{uuid4()}",
        headers=headers,
    )

    assert response.status_code == 404


def test_reading_audit_logs_does_not_modify_records(client, db_session):
    headers, admin = create_admin(db_session)

    record = create_audit_log(
        db_session,
        admin_id=admin.id,
        action="READ_ONLY_TEST",
    )

    original_created_at = record.created_at
    original_old_values = record.old_values
    original_new_values = record.new_values

    count_before = db_session.query(AuditLog).count()

    list_response = client.get(
        "/api/v1/audit-logs",
        headers=headers,
    )
    detail_response = client.get(
        f"/api/v1/audit-logs/{record.id}",
        headers=headers,
    )

    assert list_response.status_code == 200
    assert detail_response.status_code == 200

    db_session.refresh(record)

    assert db_session.query(AuditLog).count() == count_before
    assert record.created_at == original_created_at
    assert record.old_values == original_old_values
    assert record.new_values == original_new_values
