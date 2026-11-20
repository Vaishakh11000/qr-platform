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
from app.services.scan_service import (
    ProductUnavailable,
    PublishedVersionUnavailable,
    QRCodeInactive,
    QRCodeUnallocated,
    QRTokenNotFound,
    begin_scan,
    resolve_location_policy,
)


def create_region(db_session, parent=None):
    suffix = uuid4().hex[:12]
    region = Region(
        name=f"Scan Region {suffix}",
        region_code=f"SCAN-{suffix}",
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
        sku=f"SCAN-{suffix}",
        name="Scan Test Product",
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
                "title": "Published scan product",
                "description": "Test product information",
            },
            status="PUBLISHED",
            published_at=datetime.now(timezone.utc),
        )
        db_session.add(version)
        db_session.flush()

        product.current_version_id = version.id
        db_session.flush()

    return product, version


def create_qr(db_session, *, allocated=True, product=None, region=None):
    batch = QRBatch(
        batch_code=f"SCAN-{uuid4().hex}",
        quantity=1,
        generation_status="GENERATED",
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(batch)
    db_session.flush()

    qr_code = QRCode(
        batch_id=batch.id,
        token=f"scan-test-{uuid4().hex}",
        status="ACTIVE",
    )
    db_session.add(qr_code)
    db_session.flush()

    allocation = None

    if allocated:
        allocation = QRAllocation(
            qr_code_id=qr_code.id,
            product_id=product.id,
            region_id=region.id,
        )
        db_session.add(allocation)
        db_session.flush()

    return qr_code, allocation


def create_policy(
    db_session,
    *,
    scope_type,
    product_id=None,
    region_id=None,
    name=None,
    priority=0,
):
    policy = LocationPolicy(
        name=name or f"Scan Policy {uuid4().hex[:8]}",
        requirement="MANDATORY",
        method="GPS_IP_FALLBACK",
        is_active=True,
    )
    db_session.add(policy)
    db_session.flush()

    assignment = LocationPolicyAssignment(
        policy_id=policy.id,
        scope_type=scope_type,
        product_id=product_id,
        region_id=region_id,
        priority=priority,
    )
    db_session.add(assignment)
    db_session.flush()

    return policy


@pytest.mark.api
def test_begin_scan_resolves_published_product_and_records_event(db_session):
    product, version = create_product(db_session)
    region = create_region(db_session)
    qr_code, allocation = create_qr(
        db_session,
        product=product,
        region=region,
    )

    result = begin_scan(
        db_session,
        qr_code.token,
        user_agent="Scan Service Test",
        ip_hash="test-ip-hash",
    )

    assert result.product.id == product.id
    assert result.version.id == version.id
    assert result.event.qr_code_id == qr_code.id
    assert result.event.allocation_id == allocation.id
    assert result.event.product_id == product.id
    assert result.event.region_id == region.id
    assert result.event.product_version_id == version.id
    assert result.event.location_status == "PENDING"
    assert result.event.result_status == "PENDING"
    assert result.event.user_agent == "Scan Service Test"
    assert result.event.ip_hash == "test-ip-hash"

    saved_event = db_session.get(ScanEvent, result.event.id)
    assert saved_event is not None


@pytest.mark.api
def test_begin_scan_rejects_unknown_token(db_session):
    with pytest.raises(QRTokenNotFound):
        begin_scan(db_session, "unknown-scan-token")


@pytest.mark.api
def test_begin_scan_rejects_inactive_qr_code(db_session):
    product, _ = create_product(db_session)
    region = create_region(db_session)
    qr_code, _ = create_qr(
        db_session,
        product=product,
        region=region,
    )

    qr_code.status = "REVOKED"
    qr_code.deactivated_at = datetime.now(timezone.utc)
    db_session.flush()

    with pytest.raises(QRCodeInactive):
        begin_scan(db_session, qr_code.token)


@pytest.mark.api
def test_begin_scan_rejects_unallocated_qr_code(db_session):
    qr_code, _ = create_qr(db_session, allocated=False)

    with pytest.raises(QRCodeUnallocated):
        begin_scan(db_session, qr_code.token)


@pytest.mark.api
def test_begin_scan_rejects_draft_product(db_session):
    product, _ = create_product(db_session, published=False)
    region = create_region(db_session)
    qr_code, _ = create_qr(
        db_session,
        product=product,
        region=region,
    )

    with pytest.raises(ProductUnavailable):
        begin_scan(db_session, qr_code.token)


@pytest.mark.api
def test_begin_scan_rejects_product_without_published_version(db_session):
    product, _ = create_product(db_session, published=False)
    product.status = "ACTIVE"
    db_session.flush()

    region = create_region(db_session)
    qr_code, _ = create_qr(
        db_session,
        product=product,
        region=region,
    )

    with pytest.raises(PublishedVersionUnavailable):
        begin_scan(db_session, qr_code.token)


@pytest.mark.api
def test_location_policy_prefers_product_over_global(db_session):
    product, _ = create_product(db_session)
    region = create_region(db_session)

    global_policy = create_policy(
        db_session,
        scope_type="GLOBAL",
    )
    product_policy = create_policy(
        db_session,
        scope_type="PRODUCT",
        product_id=product.id,
    )

    selected = resolve_location_policy(
        db_session,
        product_id=product.id,
        region_id=None,
    )

    assert selected.id == product_policy.id
    assert selected.id != global_policy.id


@pytest.mark.api
def test_location_policy_prefers_region_over_product_and_global(db_session):
    product, _ = create_product(db_session)
    region = create_region(db_session)

    global_policy = create_policy(
        db_session,
        scope_type="GLOBAL",
    )
    product_policy = create_policy(
        db_session,
        scope_type="PRODUCT",
        product_id=product.id,
    )
    region_policy = create_policy(
        db_session,
        scope_type="REGION",
        region_id=region.id,
    )

    selected = resolve_location_policy(
        db_session,
        product_id=product.id,
        region_id=region.id,
    )

    assert selected.id == region_policy.id
    assert selected.id != product_policy.id
    assert selected.id != global_policy.id


@pytest.mark.api
def test_parent_region_policy_cascades_to_child_region(db_session):
    parent = create_region(db_session)
    child = create_region(db_session, parent=parent)
    product, _ = create_product(db_session)
    parent_policy = create_policy(
        db_session,
        scope_type="REGION",
        region_id=parent.id,
    )

    selected = resolve_location_policy(
        db_session,
        product_id=product.id,
        region_id=child.id,
    )

    assert selected is not None
    assert selected.id == parent_policy.id


@pytest.mark.api
def test_nearest_region_policy_beats_parent_even_with_lower_priority(db_session):
    root = create_region(db_session)
    parent = create_region(db_session, parent=root)
    child = create_region(db_session, parent=parent)
    product, _ = create_product(db_session)
    root_policy = create_policy(
        db_session,
        scope_type="REGION",
        region_id=root.id,
        priority=100,
    )
    parent_policy = create_policy(
        db_session,
        scope_type="REGION",
        region_id=parent.id,
        priority=0,
    )
    exact_policy = create_policy(
        db_session,
        scope_type="REGION",
        region_id=child.id,
        priority=0,
    )

    selected = resolve_location_policy(
        db_session,
        product_id=product.id,
        region_id=child.id,
    )

    assert selected is not None
    assert selected.id == exact_policy.id
    assert selected.id not in {root_policy.id, parent_policy.id}


@pytest.mark.api
def test_location_policy_uses_global_when_no_specific_policy_exists(
    db_session,
):
    product, _ = create_product(db_session)
    global_policy = create_policy(
        db_session,
        scope_type="GLOBAL",
    )

    selected = resolve_location_policy(
        db_session,
        product_id=product.id,
    )

    assert selected.id == global_policy.id


@pytest.mark.api
def test_inactive_location_policy_is_ignored(db_session):
    product, _ = create_product(db_session)

    inactive_policy = create_policy(
        db_session,
        scope_type="PRODUCT",
        product_id=product.id,
    )
    inactive_policy.is_active = False
    db_session.flush()

    selected = resolve_location_policy(
        db_session,
        product_id=product.id,
    )

    assert selected is None


@pytest.mark.api
def test_location_policy_returns_none_when_no_assignment_matches(db_session):
    product, _ = create_product(db_session)

    selected = resolve_location_policy(
        db_session,
        product_id=product.id,
        region_id=None,
    )

    assert selected is None


@pytest.mark.api
def test_begin_scan_records_region_policy_over_product_and_global(
    db_session,
):
    product, _ = create_product(db_session)
    region = create_region(db_session)

    global_policy = create_policy(
        db_session,
        scope_type="GLOBAL",
    )
    product_policy = create_policy(
        db_session,
        scope_type="PRODUCT",
        product_id=product.id,
    )
    region_policy = create_policy(
        db_session,
        scope_type="REGION",
        region_id=region.id,
    )

    qr_code, allocation = create_qr(
        db_session,
        product=product,
        region=region,
    )

    result = begin_scan(db_session, qr_code.token)

    assert result.location_policy is not None
    assert result.location_policy.id == region_policy.id
    assert result.location_policy.id != product_policy.id
    assert result.location_policy.id != global_policy.id

    assert result.event.allocation_id == allocation.id
    assert result.event.region_id == region.id
    assert result.event.location_policy_id == region_policy.id


@pytest.mark.api
def test_begin_scan_records_null_policy_when_no_policy_matches(db_session):
    product, _ = create_product(db_session)
    region = create_region(db_session)

    qr_code, _ = create_qr(
        db_session,
        product=product,
        region=region,
    )

    result = begin_scan(db_session, qr_code.token)

    assert result.location_policy is None
    assert result.event.location_policy_id is None
