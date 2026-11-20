from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models import (
    LocationPolicy,
    LocationPolicyAssignment,
    Product,
    ProductVersion,
    QRAllocation,
    QRBatch,
    QRCode,
    Region,
    ScanEvent,
)


def create_region(db_session, *, parent=None):
    suffix = uuid4().hex[:12]

    region = Region(
        name=f"Public Scan Region {suffix}",
        region_code=f"PUB-{suffix}",
        region_type="TEST",
        is_active=True,
        parent_id=parent.id if parent else None,
    )
    db_session.add(region)
    db_session.flush()
    return region


def create_product(db_session, *, published=True):
    suffix = uuid4().hex[:12]

    product = Product(
        sku=f"PUBLIC-{suffix}",
        name="Public Scan Test Product",
        status="ACTIVE" if published else "DRAFT",
    )
    db_session.add(product)
    db_session.flush()

    version = None

    if published:
        version = ProductVersion(
            product_id=product.id,
            version_number=1,
            content_snapshot={
                "title": "Test Product",
                "description": "Product information delivered by QR scan.",
            },
            status="PUBLISHED",
            published_at=datetime.now(timezone.utc),
        )
        db_session.add(version)
        db_session.flush()

        product.current_version_id = version.id
        db_session.flush()

    return product, version


def create_qr(db_session, *, product=None, region=None, allocated=True):
    batch = QRBatch(
        batch_code=f"PUBLIC-{uuid4().hex}",
        quantity=1,
        generation_status="GENERATED",
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(batch)
    db_session.flush()

    qr = QRCode(
        batch_id=batch.id,
        token=f"public-test-{uuid4().hex}",
        status="ACTIVE",
    )
    db_session.add(qr)
    db_session.flush()

    if allocated:
        allocation = QRAllocation(
            qr_code_id=qr.id,
            product_id=product.id,
            region_id=region.id,
        )
        db_session.add(allocation)
        db_session.flush()

    return qr


def create_policy(
    db_session,
    *,
    product_id=None,
    region_id=None,
    scope_type="PRODUCT",
    requirement="MANDATORY",
    method="GPS_IP_FALLBACK",
):
    policy = LocationPolicy(
        name=f"Public Scan Policy {uuid4().hex[:8]}",
        requirement=requirement,
        method=method,
        is_active=True,
    )
    db_session.add(policy)
    db_session.flush()

    assignment = LocationPolicyAssignment(
        policy_id=policy.id,
        scope_type=scope_type,
        product_id=product_id,
        region_id=region_id,
        priority=0,
    )
    db_session.add(assignment)
    db_session.flush()

    return policy


@pytest.mark.api
def test_start_scan_without_location_policy(client, db_session):
    product, _ = create_product(db_session)
    region = create_region(db_session)
    qr = create_qr(db_session, product=product, region=region)

    response = client.post(
        "/api/v1/public/scans/start",
        json={"token": qr.token},
    )

    assert response.status_code == 201

    data = response.json()
    assert data["scan_id"]
    assert data["location_requested"] is False
    assert data["location_requirement"] is None
    assert data["location_method"] is None

    event = db_session.get(ScanEvent, data["scan_id"])
    assert event is not None
    assert event.result_status == "PENDING"


@pytest.mark.api
def test_start_scan_with_product_location_policy(client, db_session):
    product, _ = create_product(db_session)
    region = create_region(db_session)
    qr = create_qr(db_session, product=product, region=region)

    create_policy(
        db_session,
        product_id=product.id,
        scope_type="PRODUCT",
        requirement="MANDATORY",
        method="GPS_REQUIRED",
    )

    response = client.post(
        "/api/v1/public/scans/start",
        json={"token": qr.token},
    )

    assert response.status_code == 201

    data = response.json()
    assert data["location_requested"] is True
    assert data["location_requirement"] == "MANDATORY"
    assert data["location_method"] == "GPS_REQUIRED"


@pytest.mark.api
def test_start_scan_uses_region_policy_over_product_policy(
    client,
    db_session,
):
    product, _ = create_product(db_session)
    region = create_region(db_session)
    qr = create_qr(db_session, product=product, region=region)

    create_policy(
        db_session,
        product_id=product.id,
        scope_type="PRODUCT",
        requirement="SKIPPABLE",
        method="GPS_REQUIRED",
    )

    create_policy(
        db_session,
        region_id=region.id,
        scope_type="REGION",
        requirement="MANDATORY",
        method="GPS_IP_FALLBACK",
    )

    response = client.post(
        "/api/v1/public/scans/start",
        json={"token": qr.token},
    )

    assert response.status_code == 201
    data = response.json()

    assert data["location_requested"] is True
    assert data["location_requirement"] == "MANDATORY"
    assert data["location_method"] == "GPS_IP_FALLBACK"


@pytest.mark.api
def test_parent_region_policy_applies_to_child_region_scan(client, db_session):
    product, _ = create_product(db_session)
    parent_region = create_region(db_session)
    child_region = create_region(db_session, parent=parent_region)
    qr = create_qr(db_session, product=product, region=child_region)
    create_policy(
        db_session,
        region_id=parent_region.id,
        scope_type="REGION",
        requirement="MANDATORY",
        method="GPS_REQUIRED",
    )

    response = client.post("/api/v1/public/scans/start", json={"token": qr.token})

    assert response.status_code == 201
    assert response.json()["location_requested"] is True
    assert response.json()["location_requirement"] == "MANDATORY"
    assert response.json()["location_method"] == "GPS_REQUIRED"


@pytest.mark.api
def test_start_scan_rejects_unknown_token(client):
    response = client.post(
        "/api/v1/public/scans/start",
        json={"token": "does-not-exist"},
    )

    assert response.status_code == 404


@pytest.mark.api
def test_start_scan_rejects_inactive_qr(client, db_session):
    product, _ = create_product(db_session)
    region = create_region(db_session)
    qr = create_qr(db_session, product=product, region=region)

    qr.status = "REVOKED"
    qr.deactivated_at = datetime.now(timezone.utc)
    db_session.flush()

    response = client.post(
        "/api/v1/public/scans/start",
        json={"token": qr.token},
    )

    assert response.status_code == 409


@pytest.mark.api
def test_start_scan_rejects_unallocated_qr(client, db_session):
    qr = create_qr(db_session, allocated=False)

    response = client.post(
        "/api/v1/public/scans/start",
        json={"token": qr.token},
    )

    assert response.status_code == 409


@pytest.mark.api
def test_start_scan_rejects_draft_product(client, db_session):
    product, _ = create_product(db_session, published=False)
    region = create_region(db_session)
    qr = create_qr(db_session, product=product, region=region)

    response = client.post(
        "/api/v1/public/scans/start",
        json={"token": qr.token},
    )

    assert response.status_code == 409


@pytest.mark.api
def test_complete_scan_returns_published_product(client, db_session):
    product, version = create_product(db_session)
    region = create_region(db_session)
    qr = create_qr(db_session, product=product, region=region)

    start = client.post(
        "/api/v1/public/scans/start",
        json={"token": qr.token},
    )
    assert start.status_code == 201

    scan_id = start.json()["scan_id"]

    completion = client.post(
        f"/api/v1/public/scans/{scan_id}/location",
        json={"location_status": "SKIPPED"},
    )

    assert completion.status_code == 200

    data = completion.json()
    assert data["scan_id"] == scan_id
    assert data["result_status"] == "ALLOWED"
    assert data["location_status"] == "SKIPPED"
    assert data["product"]["id"] == str(product.id)
    assert data["product"]["sku"] == product.sku
    assert data["product"]["name"] == product.name
    assert data["product"]["content_snapshot"] == version.content_snapshot


@pytest.mark.api
def test_public_product_snapshot_hides_internal_seed_notes(client, db_session):
    product, version = create_product(db_session)
    version.content_snapshot = {
        "title": "Test Product",
        "specifications": {
            "model": "AX-100",
            "data_quality_note": "Internal source mismatch",
        },
        "example": "Illustrative content only",
        "data_quality_note": "Confirm dimensions before publishing",
    }
    db_session.flush()
    region = create_region(db_session)
    qr = create_qr(db_session, product=product, region=region)

    start = client.post(
        "/api/v1/public/scans/start",
        json={"token": qr.token},
    )
    assert start.status_code == 201
    scan_id = start.json()["scan_id"]

    completion = client.post(
        f"/api/v1/public/scans/{scan_id}/location",
        json={"location_status": "SKIPPED"},
    )

    assert completion.status_code == 200
    assert completion.json()["product"]["content_snapshot"] == {
        "title": "Test Product",
        "specifications": {"model": "AX-100"},
    }


@pytest.mark.api
def test_mandatory_location_blocks_scan_without_gps(client, db_session):
    product, _ = create_product(db_session)
    region = create_region(db_session)
    qr = create_qr(db_session, product=product, region=region)

    create_policy(
        db_session,
        product_id=product.id,
        scope_type="PRODUCT",
        requirement="MANDATORY",
    )

    start = client.post(
        "/api/v1/public/scans/start",
        json={"token": qr.token},
    )
    assert start.status_code == 201

    scan_id = start.json()["scan_id"]

    completion = client.post(
        f"/api/v1/public/scans/{scan_id}/location",
        json={"location_status": "DENIED"},
    )

    assert completion.status_code == 200

    data = completion.json()
    assert data["result_status"] == "BLOCKED"
    assert data["product"] is None
    assert "saved this site's location permission as blocked" in data["message"]
    assert "tap Try again" in data["message"]
    assert "IP-based fallback is not configured" in data["message"]


@pytest.mark.api
def test_skippable_location_allows_scan_without_gps(client, db_session):
    product, _ = create_product(db_session)
    region = create_region(db_session)
    qr = create_qr(db_session, product=product, region=region)

    create_policy(
        db_session,
        product_id=product.id,
        scope_type="PRODUCT",
        requirement="SKIPPABLE",
    )

    start = client.post(
        "/api/v1/public/scans/start",
        json={"token": qr.token},
    )
    assert start.status_code == 201

    scan_id = start.json()["scan_id"]

    completion = client.post(
        f"/api/v1/public/scans/{scan_id}/location",
        json={"location_status": "SKIPPED"},
    )

    assert completion.status_code == 200

    data = completion.json()
    assert data["result_status"] == "ALLOWED"
    assert data["product"] is not None
    assert data["product"]["id"] == str(product.id)


@pytest.mark.api
def test_gps_scan_returns_product(client, db_session):
    product, _ = create_product(db_session)
    region = create_region(db_session)
    qr = create_qr(db_session, product=product, region=region)

    create_policy(
        db_session,
        product_id=product.id,
        scope_type="PRODUCT",
        requirement="MANDATORY",
        method="GPS_REQUIRED",
    )

    start = client.post(
        "/api/v1/public/scans/start",
        json={"token": qr.token},
    )
    assert start.status_code == 201

    scan_id = start.json()["scan_id"]

    completion = client.post(
        f"/api/v1/public/scans/{scan_id}/location",
        json={
            "location_status": "GPS",
            "latitude": 19.076,
            "longitude": 72.8777,
            "accuracy_meters": 25,
        },
    )

    assert completion.status_code == 200

    data = completion.json()
    assert data["result_status"] == "ALLOWED"
    assert data["location_status"] == "GPS"
    assert data["product"] is not None


@pytest.mark.api
def test_invalid_gps_coordinates_return_422(client, db_session):
    product, _ = create_product(db_session)
    region = create_region(db_session)
    qr = create_qr(db_session, product=product, region=region)

    start = client.post(
        "/api/v1/public/scans/start",
        json={"token": qr.token},
    )
    assert start.status_code == 201

    scan_id = start.json()["scan_id"]

    completion = client.post(
        f"/api/v1/public/scans/{scan_id}/location",
        json={
            "location_status": "GPS",
            "latitude": 120,
            "longitude": 72.8777,
        },
    )

    assert completion.status_code == 422


@pytest.mark.api
def test_completion_rejects_unknown_scan_session(client):
    response = client.post(
        f"/api/v1/public/scans/{uuid4()}/location",
        json={"location_status": "SKIPPED"},
    )

    assert response.status_code == 404


@pytest.mark.api
def test_scan_session_cannot_be_completed_twice(client, db_session):
    product, _ = create_product(db_session)
    region = create_region(db_session)
    qr = create_qr(db_session, product=product, region=region)

    start = client.post(
        "/api/v1/public/scans/start",
        json={"token": qr.token},
    )
    assert start.status_code == 201

    scan_id = start.json()["scan_id"]
    payload = {"location_status": "SKIPPED"}

    first = client.post(
        f"/api/v1/public/scans/{scan_id}/location",
        json=payload,
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/public/scans/{scan_id}/location",
        json=payload,
    )
    assert second.status_code == 409


@pytest.mark.api
def test_public_qr_page_does_not_create_scan_event(client, db_session):
    product, _ = create_product(db_session)
    region = create_region(db_session)
    qr = create_qr(db_session, product=product, region=region)

    before = db_session.query(ScanEvent).count()

    response = client.get(f"/q/{qr.token}")

    after = db_session.query(ScanEvent).count()

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'allowButton.addEventListener("click", requestLocation)' in response.text
    assert "controls.hidden = false;" in response.text
    assert 'allowButton.textContent = "Try location again";' in response.text
    assert after == before
