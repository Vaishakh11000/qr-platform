from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.security import create_access_token, hash_password
from app.models import (
    AdminUser,
    AuditLog,
    Product,
    QRBatch,
    QRCode,
    Role,
    ScanEvent,
)


def create_admin(db, role_name="SUPER_ADMIN"):
    role = db.query(Role).filter_by(name=role_name).one_or_none()

    if role is None:
        role = Role(
            name=role_name,
            description="Dashboard API test role",
        )
        db.add(role)
        db.flush()

    admin = AdminUser(
        name="Dashboard Test Admin",
        email=f"{uuid4().hex}@example.test",
        password_hash=hash_password("Test-Password-123!"),
        role_id=role.id,
        is_active=True,
    )
    db.add(admin)
    db.flush()

    token = create_access_token(admin.id)
    return {"Authorization": f"Bearer {token}"}, admin


def create_scan(
    db,
    qr_code_id,
    *,
    result_status="PENDING",
    location_status="PENDING",
    scanned_at=None,
):
    scan = ScanEvent(
        qr_code_id=qr_code_id,
        result_status=result_status,
        location_status=location_status,
    )

    if scanned_at is not None:
        scan.scanned_at = scanned_at

    db.add(scan)
    db.flush()
    return scan


def test_dashboard_overview_requires_authentication(client):
    response = client.get("/api/v1/dashboard/overview")
    assert response.status_code == 401


def test_dashboard_rejects_non_super_admin(client, db_session):
    headers, _ = create_admin(db_session, "CONTENT_EDITOR")

    response = client.get(
        "/api/v1/dashboard/overview",
        headers=headers,
    )

    assert response.status_code == 403


def test_dashboard_overview_returns_source_table_counts(
    client,
    db_session,
):
    headers, _ = create_admin(db_session)

    db_session.add_all([
        Product(sku="DASH-ACTIVE", name="Active Product", status="ACTIVE"),
        Product(sku="DASH-DRAFT", name="Draft Product", status="DRAFT"),
        Product(sku="DASH-ARCHIVED", name="Archived Product", status="ARCHIVED"),
    ])

    generated_batch = QRBatch(
        batch_code=f"DASH-GEN-{uuid4().hex[:8]}",
        quantity=2,
        generation_status="GENERATED",
    )
    pending_batch = QRBatch(
        batch_code=f"DASH-PEND-{uuid4().hex[:8]}",
        quantity=1,
        generation_status="PENDING",
    )
    failed_batch = QRBatch(
        batch_code=f"DASH-FAIL-{uuid4().hex[:8]}",
        quantity=1,
        generation_status="FAILED",
    )

    db_session.add_all([generated_batch, pending_batch, failed_batch])
    db_session.flush()

    db_session.add_all([
        QRCode(
            batch_id=generated_batch.id,
            token=f"dash-active-{uuid4().hex}",
            status="ACTIVE",
        ),
        QRCode(
            batch_id=generated_batch.id,
            token=f"dash-inactive-{uuid4().hex}",
            status="INACTIVE",
            deactivated_at=datetime.now(timezone.utc),
        ),
        QRCode(
            batch_id=generated_batch.id,
            token=f"dash-revoked-{uuid4().hex}",
            status="REVOKED",
            deactivated_at=datetime.now(timezone.utc),
        ),
    ])
    db_session.flush()

    qr_code = (
        db_session.query(QRCode)
        .filter(QRCode.status == "ACTIVE")
        .one()
    )

    create_scan(
        db_session,
        qr_code.id,
        result_status="ALLOWED",
        location_status="GPS",
    )
    create_scan(
        db_session,
        qr_code.id,
        result_status="BLOCKED",
        location_status="SKIPPED",
    )
    create_scan(
        db_session,
        qr_code.id,
        result_status="ERROR",
        location_status="UNAVAILABLE",
    )
    create_scan(
        db_session,
        qr_code.id,
        result_status="PENDING",
        location_status="PENDING",
    )

    response = client.get(
        "/api/v1/dashboard/overview",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["products"] == {
        "total": 3,
        "active": 1,
        "draft": 1,
        "archived": 1,
    }

    assert data["qr_codes"] == {
        "total": 3,
        "active": 1,
        "inactive": 1,
        "revoked": 1,
        "allocated": 0,
    }

    assert data["batches"] == {
        "total": 3,
        "generated": 1,
        "pending": 1,
        "failed": 1,
    }

    assert data["scans"] == {
        "total": 4,
        "pending": 1,
        "allowed": 1,
        "blocked": 1,
        "error": 1,
    }


def test_dashboard_scan_trends_groups_scans_by_utc_date(
    client,
    db_session,
):
    headers, _ = create_admin(db_session)

    batch = QRBatch(
        batch_code=f"DASH-TREND-{uuid4().hex[:8]}",
        quantity=1,
        generation_status="GENERATED",
    )
    db_session.add(batch)
    db_session.flush()

    qr_code = QRCode(
        batch_id=batch.id,
        token=f"dash-trend-{uuid4().hex}",
        status="ACTIVE",
    )
    db_session.add(qr_code)
    db_session.flush()

    today = datetime.now(timezone.utc).date()

    create_scan(
        db_session,
        qr_code.id,
        result_status="ALLOWED",
        scanned_at=datetime.combine(
            today,
            datetime.min.time(),
            tzinfo=timezone.utc,
        ) + timedelta(hours=10),
    )

    create_scan(
        db_session,
        qr_code.id,
        result_status="BLOCKED",
        scanned_at=datetime.combine(
            today,
            datetime.min.time(),
            tzinfo=timezone.utc,
        ) + timedelta(hours=11),
    )

    yesterday = today - timedelta(days=1)

    create_scan(
        db_session,
        qr_code.id,
        result_status="PENDING",
        scanned_at=datetime.combine(
            yesterday,
            datetime.min.time(),
            tzinfo=timezone.utc,
        ) + timedelta(hours=8),
    )

    response = client.get(
        "/api/v1/dashboard/scan-trends",
        params={"days": 3},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 3
    assert [item["date"] for item in data] == [
        str(today - timedelta(days=2)),
        str(today - timedelta(days=1)),
        str(today),
    ]

    assert data[0]["total"] == 0
    assert data[1]["total"] == 1
    assert data[1]["pending"] == 1
    assert data[2]["total"] == 2
    assert data[2]["allowed"] == 1
    assert data[2]["blocked"] == 1


def test_dashboard_scan_trends_rejects_invalid_days(client, db_session):
    headers, _ = create_admin(db_session)

    response = client.get(
        "/api/v1/dashboard/scan-trends",
        params={"days": 0},
        headers=headers,
    )

    assert response.status_code == 422


def test_dashboard_location_analytics_returns_status_counts(
    client,
    db_session,
):
    headers, _ = create_admin(db_session)

    batch = QRBatch(
        batch_code=f"DASH-LOC-{uuid4().hex[:8]}",
        quantity=1,
        generation_status="GENERATED",
    )
    db_session.add(batch)
    db_session.flush()

    qr_code = QRCode(
        batch_id=batch.id,
        token=f"dash-location-{uuid4().hex}",
        status="ACTIVE",
    )
    db_session.add(qr_code)
    db_session.flush()

    create_scan(
        db_session,
        qr_code.id,
        location_status="GPS",
    )
    create_scan(
        db_session,
        qr_code.id,
        location_status="SKIPPED",
    )
    create_scan(
        db_session,
        qr_code.id,
        location_status="DENIED",
    )
    create_scan(
        db_session,
        qr_code.id,
        location_status="IP_LOOKUP_FAILED",
    )

    response = client.get(
        "/api/v1/dashboard/location-analytics",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["location_statuses"]["GPS"] == 1
    assert data["location_statuses"]["SKIPPED"] == 1
    assert data["location_statuses"]["DENIED"] == 1
    assert data["location_statuses"]["IP_LOOKUP_FAILED"] == 1
    assert data["location_statuses"]["IP_DERIVED"] == 0

    assert data["classifications"] == {
        "MATCH": 0,
        "MISMATCH": 0,
        "UNKNOWN": 0,
        "NOT_CHECKED": 0,
    }


def test_dashboard_recent_activity_excludes_sensitive_audit_fields(
    client,
    db_session,
):
    headers, admin = create_admin(db_session)

    record = AuditLog(
        admin_id=admin.id,
        action="PRODUCT_UPDATED",
        entity_type="PRODUCT",
        entity_id=uuid4(),
        old_values={"private": "old-value"},
        new_values={"private": "new-value"},
        ip_hash="private-ip-hash",
    )
    db_session.add(record)
    db_session.flush()

    response = client.get(
        "/api/v1/dashboard/recent-activity",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    item = data[0]

    assert item["id"] == str(record.id)
    assert item["admin_id"] == str(admin.id)
    assert item["action"] == "PRODUCT_UPDATED"
    assert item["entity_type"] == "PRODUCT"

    assert "old_values" not in item
    assert "new_values" not in item
    assert "ip_hash" not in item
    assert "private-ip-hash" not in str(item)


def test_dashboard_recent_activity_validates_limit(client, db_session):
    headers, _ = create_admin(db_session)

    response = client.get(
        "/api/v1/dashboard/recent-activity",
        params={"limit": 101},
        headers=headers,
    )

    assert response.status_code == 422
