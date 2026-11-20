from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models import (
    Product,
    ProductVersion,
    QRAllocation,
    QRBatch,
    QRCode,
    Region,
    ScanClassification,
    ScanEvent,
)


def create_scan_fixture(db):
    suffix = uuid4().hex[:10]
    product = Product(sku=f"AN-{suffix}", name=f"Analytics product {suffix}", status="ACTIVE")
    region = Region(
        name=f"Analytics region {suffix}",
        region_code=f"AN-{suffix}",
        region_type="TEST",
        is_active=True,
    )
    batch = QRBatch(batch_code=f"AN-{suffix}", quantity=1, generation_status="GENERATED")
    db.add_all([product, region, batch])
    db.flush()

    version = ProductVersion(
        product_id=product.id,
        version_number=1,
        content_snapshot={"title": "Analytics test"},
        status="PUBLISHED",
        published_at=datetime.now(timezone.utc),
    )
    db.add(version)
    db.flush()
    product.current_version_id = version.id

    qr_code = QRCode(batch_id=batch.id, token=f"analytics-{uuid4().hex}", status="ACTIVE")
    db.add(qr_code)
    db.flush()
    allocation = QRAllocation(
        qr_code_id=qr_code.id,
        product_id=product.id,
        region_id=region.id,
    )
    db.add(allocation)
    db.flush()

    today = datetime.now(timezone.utc).date()
    first = ScanEvent(
        qr_code_id=qr_code.id,
        allocation_id=allocation.id,
        product_id=product.id,
        region_id=region.id,
        product_version_id=version.id,
        result_status="ALLOWED",
        location_status="GPS",
        scanned_at=datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=8),
    )
    second = ScanEvent(
        qr_code_id=qr_code.id,
        allocation_id=allocation.id,
        product_id=product.id,
        region_id=region.id,
        product_version_id=version.id,
        result_status="BLOCKED",
        location_status="DENIED",
        scanned_at=datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=9),
    )
    previous_day = ScanEvent(
        qr_code_id=qr_code.id,
        allocation_id=allocation.id,
        product_id=product.id,
        region_id=region.id,
        product_version_id=version.id,
        result_status="ALLOWED",
        location_status="SKIPPED",
        scanned_at=datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=23),
    )
    db.add_all([first, second, previous_day])
    db.flush()
    db.add_all([
        ScanClassification(
            scan_event_id=first.id,
            assigned_region_id=region.id,
            detected_region_id=region.id,
            classification="MATCH",
        ),
        ScanClassification(
            scan_event_id=second.id,
            assigned_region_id=region.id,
            classification="MISMATCH",
        ),
    ])
    db.flush()
    return product, region, qr_code, today


def test_scan_analytics_returns_stored_product_region_qr_and_location_counts(
    admin_client,
    db_session,
):
    product, region, qr_code, today = create_scan_fixture(db_session)
    response = admin_client.get(
        "/api/v1/analytics/scans",
        params={"from_date": str(today - timedelta(days=1)), "to_date": str(today)},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == {
        "total": 3, "pending": 0, "allowed": 2, "blocked": 1, "error": 0,
    }
    assert [day["total"] for day in data["daily"]] == [1, 2]
    assert data["products"][0]["product_id"] == str(product.id)
    assert data["products"][0]["scans"] == 3
    assert data["regions"][0]["region_id"] == str(region.id)
    assert data["regions"][0]["scans"] == 3
    assert data["qr_codes"][0]["qr_code_id"] == str(qr_code.id)
    assert data["qr_codes"][0]["scans"] == 3
    assert len(data["qr_codes"][0]["token_suffix"]) == 6
    assert data["location_analytics"]["location_statuses"]["GPS"] == 1
    assert data["location_analytics"]["location_statuses"]["DENIED"] == 1
    assert data["location_analytics"]["classifications"]["MATCH"] == 1
    assert data["location_analytics"]["classifications"]["MISMATCH"] == 1


def test_scan_analytics_filters_by_product_qr_region_and_outcome(
    admin_client,
    db_session,
):
    product, region, qr_code, today = create_scan_fixture(db_session)
    response = admin_client.get(
        "/api/v1/analytics/scans",
        params={
            "from_date": str(today),
            "to_date": str(today),
            "product_id": str(product.id),
            "qr_code_id": str(qr_code.id),
            "region_id": str(region.id),
            "result_status": "BLOCKED",
            "location_status": "DENIED",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total"] == 1
    assert data["summary"]["blocked"] == 1
    assert data["daily"] == [{
        "date": str(today), "total": 1, "pending": 0,
        "allowed": 0, "blocked": 1, "error": 0,
    }]
    assert data["location_analytics"]["location_statuses"]["DENIED"] == 1
    assert data["qr_codes"][0]["scans"] == 1


def test_scan_analytics_requires_authentication(client):
    assert client.get("/api/v1/analytics/scans").status_code == 401


def test_scan_analytics_rejects_invalid_range_and_status(admin_client):
    assert admin_client.get(
        "/api/v1/analytics/scans",
        params={"from_date": "2026-02-02", "to_date": "2026-02-01"},
    ).status_code == 422
    assert admin_client.get(
        "/api/v1/analytics/scans",
        params={"result_status": "SUCCESS"},
    ).status_code == 422
    assert admin_client.get(
        "/api/v1/analytics/scans",
        params={"from_date": "2024-01-01", "to_date": "2026-01-01"},
    ).status_code == 422
