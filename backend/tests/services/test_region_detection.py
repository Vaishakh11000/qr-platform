from datetime import datetime, timezone
from uuid import uuid4

import pytest
from geoalchemy2.elements import WKTElement

from app.models import (
    Product,
    ProductVersion,
    QRAllocation,
    QRBatch,
    QRCode,
    Region,
    RegionBoundary,
    ScanClassification,
    ScanLocation,
)
from app.schemas.public_scan import ScanLocationSubmission
from app.services.region_detection_service import (
    classify_region,
    detect_region,
    resolve_scan_region,
)
from app.services.scan_service import begin_scan, complete_scan


def create_region(db_session, *, parent=None):
    suffix = uuid4().hex[:12]

    region = Region(
        name=f"Geo Test {suffix}",
        region_code=f"GEO-{suffix}",
        region_type="TEST",
        parent_id=parent.id if parent else None,
        is_active=True,
    )
    db_session.add(region)
    db_session.flush()
    return region


def create_boundary(db_session, region, west, south, east, north):
    wkt = (
        "MULTIPOLYGON((("
        f"{west} {south},"
        f"{east} {south},"
        f"{east} {north},"
        f"{west} {north},"
        f"{west} {south}"
        ")))"
    )

    boundary = RegionBoundary(
        region_id=region.id,
        boundary=WKTElement(wkt, srid=4326),
    )
    db_session.add(boundary)
    db_session.flush()
    return boundary


@pytest.mark.api
def test_detects_region_containing_gps_point(db_session):
    region = create_region(db_session)
    create_boundary(db_session, region, 72, 18, 74, 20)

    detected = detect_region(
        db_session,
        latitude=19.076,
        longitude=72.8777,
    )

    assert detected is not None
    assert detected.id == region.id


@pytest.mark.api
def test_detects_deepest_nested_region(db_session):
    parent = create_region(db_session)
    child = create_region(db_session, parent=parent)

    create_boundary(db_session, parent, 72, 18, 74, 20)
    create_boundary(db_session, child, 72.7, 18.8, 73.0, 19.3)

    detected = detect_region(
        db_session,
        latitude=19.076,
        longitude=72.8777,
    )

    assert detected is not None
    assert detected.id == child.id


@pytest.mark.api
def test_point_on_boundary_is_included(db_session):
    region = create_region(db_session)
    create_boundary(db_session, region, 72, 18, 74, 20)

    detected = detect_region(
        db_session,
        latitude=19.0,
        longitude=72.0,
    )

    assert detected is not None
    assert detected.id == region.id


@pytest.mark.api
def test_returns_none_when_point_is_outside_all_boundaries(db_session):
    region = create_region(db_session)
    create_boundary(db_session, region, 72, 18, 74, 20)

    detected = detect_region(
        db_session,
        latitude=25.0,
        longitude=80.0,
    )

    assert detected is None


@pytest.mark.api
def test_ambiguous_overlapping_sibling_regions_return_none(db_session):
    parent = create_region(db_session)
    first = create_region(db_session, parent=parent)
    second = create_region(db_session, parent=parent)

    create_boundary(db_session, parent, 72, 18, 75, 21)
    create_boundary(db_session, first, 72.5, 18.5, 73.5, 19.5)
    create_boundary(db_session, second, 72.7, 18.7, 73.7, 19.7)

    detected = detect_region(
        db_session,
        latitude=19.0,
        longitude=73.0,
    )

    assert detected is None


@pytest.mark.api
def test_parent_allocation_matches_descendant_scan(db_session):
    parent = create_region(db_session)
    child = create_region(db_session, parent=parent)

    assert classify_region(
        db_session,
        assigned_region_id=parent.id,
        detected_region_id=child.id,
    ) == "MATCH"


@pytest.mark.api
def test_child_allocation_does_not_match_parent_scan(db_session):
    parent = create_region(db_session)
    child = create_region(db_session, parent=parent)

    assert classify_region(
        db_session,
        assigned_region_id=child.id,
        detected_region_id=parent.id,
    ) == "MISMATCH"


@pytest.mark.api
def test_unrelated_regions_are_mismatch(db_session):
    first = create_region(db_session)
    second = create_region(db_session)

    assert classify_region(
        db_session,
        assigned_region_id=first.id,
        detected_region_id=second.id,
    ) == "MISMATCH"


@pytest.mark.api
@pytest.mark.parametrize(
    "accuracy",
    [None, 501, 1000],
)
def test_poor_or_missing_accuracy_returns_unknown(db_session, accuracy):
    region = create_region(db_session)
    create_boundary(db_session, region, 72, 18, 74, 20)

    detected, classification = resolve_scan_region(
        db_session,
        assigned_region_id=region.id,
        latitude=19.076,
        longitude=72.8777,
        accuracy_meters=accuracy,
    )

    assert detected is None
    assert classification == "UNKNOWN"


@pytest.mark.api
def test_no_boundary_returns_unknown(db_session):
    region = create_region(db_session)

    detected, classification = resolve_scan_region(
        db_session,
        assigned_region_id=region.id,
        latitude=19.076,
        longitude=72.8777,
        accuracy_meters=20,
    )

    assert detected is None
    assert classification == "UNKNOWN"


@pytest.mark.api
def test_gps_scan_persists_region_and_classification(db_session):
    parent = create_region(db_session)
    child = create_region(db_session, parent=parent)

    create_boundary(db_session, parent, 72, 18, 74, 20)
    create_boundary(db_session, child, 72.7, 18.8, 73.0, 19.3)

    suffix = uuid4().hex[:12]

    product = Product(
        sku=f"GEO-PRODUCT-{suffix}",
        name="Geographic Integration Test",
        status="ACTIVE",
    )
    db_session.add(product)
    db_session.flush()

    version = ProductVersion(
        product_id=product.id,
        version_number=1,
        content_snapshot={"title": "Geographic test"},
        status="PUBLISHED",
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(version)
    db_session.flush()

    product.current_version_id = version.id
    db_session.flush()

    batch = QRBatch(
        batch_code=f"GEO-BATCH-{suffix}",
        quantity=1,
        generation_status="GENERATED",
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(batch)
    db_session.flush()

    qr = QRCode(
        batch_id=batch.id,
        token=f"geo-token-{suffix}",
        status="ACTIVE",
    )
    db_session.add(qr)
    db_session.flush()

    allocation = QRAllocation(
        qr_code_id=qr.id,
        product_id=product.id,
        region_id=parent.id,
    )
    db_session.add(allocation)
    db_session.flush()

    started = begin_scan(db_session, qr.token)

    submission = ScanLocationSubmission(
        location_status="GPS",
        latitude=19.076,
        longitude=72.8777,
        accuracy_meters=20,
    )

    completed, _ = complete_scan(
        db_session,
        started.event.id,
        submission,
    )

    assert completed.result_status == "ALLOWED"

    location = db_session.query(ScanLocation).filter_by(
        scan_event_id=started.event.id
    ).one()

    classification = db_session.query(ScanClassification).filter_by(
        scan_event_id=started.event.id
    ).one()

    assert location.resolved_region_id == child.id
    assert classification.assigned_region_id == parent.id
    assert classification.detected_region_id == child.id
    assert classification.classification == "MATCH"
