from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models import (
    LocationPolicy,
    QRBatch,
    QRCode,
    ScanEvent,
    ScanLocation,
)
from app.schemas.public_scan import ScanLocationSubmission
from app.services.scan_service import (
    ScanAlreadyCompleted,
    ScanEventNotFound,
    InvalidScanLocation,
    complete_scan,
)


def create_scan_event(db_session, policy=None):
    batch = QRBatch(
        batch_code=f"COMPLETE-{uuid4().hex}",
        quantity=1,
        generation_status="GENERATED",
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(batch)
    db_session.flush()

    qr = QRCode(
        batch_id=batch.id,
        token=f"complete-{uuid4().hex}",
    )
    db_session.add(qr)
    db_session.flush()

    event = ScanEvent(
        qr_code_id=qr.id,
        location_policy_id=policy.id if policy else None,
        location_status="PENDING",
        result_status="PENDING",
    )
    db_session.add(event)
    db_session.flush()

    return event


def create_policy(db_session, requirement, method="GPS_IP_FALLBACK"):
    policy = LocationPolicy(
        name=f"Completion Policy {uuid4().hex[:8]}",
        requirement=requirement,
        method=method,
        is_active=True,
    )
    db_session.add(policy)
    db_session.flush()
    return policy


@pytest.mark.api
def test_gps_location_completes_scan(db_session):
    policy = create_policy(db_session, "MANDATORY")
    event = create_scan_event(db_session, policy)

    submission = ScanLocationSubmission(
        location_status="GPS",
        latitude=19.076,
        longitude=72.8777,
        accuracy_meters=20,
    )

    completed, message = complete_scan(
        db_session,
        event.id,
        submission,
    )

    assert completed.result_status == "ALLOWED"
    assert completed.location_status == "GPS"
    assert completed.completed_at is not None
    assert "successfully" in message

    location = db_session.query(ScanLocation).filter_by(
        scan_event_id=event.id
    ).one()

    assert location.source == "GPS"
    assert float(location.latitude) == pytest.approx(19.076)
    assert float(location.longitude) == pytest.approx(72.8777)
    assert location.confidence == "HIGH"


@pytest.mark.api
def test_mandatory_location_blocks_skipped_scan(db_session):
    policy = create_policy(db_session, "MANDATORY")
    event = create_scan_event(db_session, policy)

    submission = ScanLocationSubmission(
        location_status="SKIPPED",
    )

    completed, _ = complete_scan(db_session, event.id, submission)

    assert completed.result_status == "BLOCKED"
    assert completed.location_status == "IP_LOOKUP_FAILED"
    assert completed.completed_at is not None


@pytest.mark.api
def test_mandatory_location_blocks_denied_scan(db_session):
    policy = create_policy(db_session, "MANDATORY")
    event = create_scan_event(db_session, policy)

    submission = ScanLocationSubmission(
        location_status="DENIED",
    )

    completed, _ = complete_scan(db_session, event.id, submission)

    assert completed.result_status == "BLOCKED"
    assert completed.location_status == "IP_LOOKUP_FAILED"


@pytest.mark.api
def test_skippable_location_allows_scan_without_gps(db_session):
    policy = create_policy(db_session, "SKIPPABLE")
    event = create_scan_event(db_session, policy)

    submission = ScanLocationSubmission(
        location_status="SKIPPED",
    )

    completed, message = complete_scan(
        db_session,
        event.id,
        submission,
    )

    assert completed.result_status == "ALLOWED"
    assert completed.location_status == "IP_LOOKUP_FAILED"
    assert "permitted" in message


@pytest.mark.api
def test_scan_without_policy_allows_skipped_location(db_session):
    event = create_scan_event(db_session)

    submission = ScanLocationSubmission(
        location_status="SKIPPED",
    )

    completed, _ = complete_scan(db_session, event.id, submission)

    assert completed.result_status == "ALLOWED"
    assert completed.location_status == "SKIPPED"


@pytest.mark.api
def test_ip_only_policy_rejects_browser_gps(db_session):
    policy = create_policy(
        db_session,
        "MANDATORY",
        method="IP_ONLY",
    )
    event = create_scan_event(db_session, policy)

    submission = ScanLocationSubmission(
        location_status="GPS",
        latitude=19.076,
        longitude=72.8777,
    )

    with pytest.raises(InvalidScanLocation):
        complete_scan(db_session, event.id, submission)


@pytest.mark.api
def test_inactive_policy_rejects_scan_completion(db_session):
    policy = create_policy(db_session, "MANDATORY")
    event = create_scan_event(db_session, policy)

    policy.is_active = False
    db_session.flush()

    submission = ScanLocationSubmission(
        location_status="GPS",
        latitude=19.076,
        longitude=72.8777,
    )

    with pytest.raises(InvalidScanLocation):
        complete_scan(db_session, event.id, submission)


@pytest.mark.api
def test_scan_cannot_be_completed_twice(db_session):
    event = create_scan_event(db_session)

    submission = ScanLocationSubmission(
        location_status="SKIPPED",
    )

    complete_scan(db_session, event.id, submission)

    with pytest.raises(ScanAlreadyCompleted):
        complete_scan(db_session, event.id, submission)


@pytest.mark.api
def test_nonexistent_scan_event_returns_not_found(db_session):
    submission = ScanLocationSubmission(
        location_status="SKIPPED",
    )

    with pytest.raises(ScanEventNotFound):
        complete_scan(db_session, uuid4(), submission)


@pytest.mark.api
def test_invalid_coordinates_are_rejected_by_schema():
    with pytest.raises(ValueError):
        ScanLocationSubmission(
            location_status="GPS",
            latitude=120,
            longitude=72.8777,
        )

    with pytest.raises(ValueError):
        ScanLocationSubmission(
            location_status="GPS",
            latitude=19.076,
        )

    with pytest.raises(ValueError):
        ScanLocationSubmission(
            location_status="SKIPPED",
            latitude=19.076,
            longitude=72.8777,
        )
