
from datetime import datetime, timezone

import pytest

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import (
    Product,
    Region,
    QRBatch,
    QRCode,
    QRAllocation,
)


def create_qr_dependencies(db_session, suffix):
    """
    Create the minimum records required for a QR allocation.

    All records are created inside the isolated test transaction.
    """

    product = Product(
        sku=f"TEST-SKU-{suffix}",
        name=f"Test Product {suffix}",
    )
    db_session.add(product)
    db_session.flush()

    region = Region(
        name=f"Test Region {suffix}",
        region_code=f"TEST-REGION-{suffix}",
        region_type="TEST",
    )
    db_session.add(region)
    db_session.flush()

    batch = QRBatch(
        batch_code=f"TEST-BATCH-{suffix}",
        requested_product_id=product.id,
        requested_region_id=region.id,
        quantity=1,
    )
    db_session.add(batch)
    db_session.flush()

    qr_code = QRCode(
        batch_id=batch.id,
        token=f"TEST-TOKEN-{suffix}",
    )
    db_session.add(qr_code)
    db_session.flush()

    return product, region, qr_code


@pytest.mark.integration
def test_overlapping_qr_allocations_are_rejected(db_session):
    """
    The same QR code cannot have overlapping allocation periods.
    """

    product, region, qr_code = create_qr_dependencies(
        db_session,
        "OVERLAP",
    )

    first_allocation = QRAllocation(
        qr_code_id=qr_code.id,
        product_id=product.id,
        region_id=region.id,
        assigned_at=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
    )

    db_session.add(first_allocation)
    db_session.flush()

    overlapping_allocation = QRAllocation(
        qr_code_id=qr_code.id,
        product_id=product.id,
        region_id=region.id,
        assigned_at=datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc),
    )

    db_session.add(overlapping_allocation)

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_consecutive_qr_allocations_are_allowed(db_session):
    """
    An allocation ending exactly when another begins is valid.
    """

    product, region, qr_code = create_qr_dependencies(
        db_session,
        "CONSECUTIVE",
    )

    first_allocation = QRAllocation(
        qr_code_id=qr_code.id,
        product_id=product.id,
        region_id=region.id,
        assigned_at=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
    )

    second_allocation = QRAllocation(
        qr_code_id=qr_code.id,
        product_id=product.id,
        region_id=region.id,
        assigned_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 1, 1, 14, 0, tzinfo=timezone.utc),
    )

    db_session.add_all([
        first_allocation,
        second_allocation,
    ])
    db_session.flush()

    allocation_count = db_session.scalar(
        select(func.count())
        .select_from(QRAllocation)
        .where(QRAllocation.qr_code_id == qr_code.id)
    )

    assert allocation_count == 2

@pytest.mark.integration
def test_allocation_end_must_be_after_start(db_session):
    """
    An allocation with ended_at equal to assigned_at is invalid.
    """

    product, region, qr_code = create_qr_dependencies(
        db_session,
        "INVALID-TIME",
    )

    allocation = QRAllocation(
        qr_code_id=qr_code.id,
        product_id=product.id,
        region_id=region.id,
        assigned_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
    )

    db_session.add(allocation)

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_only_one_active_allocation_per_qr(db_session):
    """
    A QR code cannot have multiple allocations with ended_at NULL.
    """

    product, region, qr_code = create_qr_dependencies(
        db_session,
        "MULTIPLE-ACTIVE",
    )

    first_allocation = QRAllocation(
        qr_code_id=qr_code.id,
        product_id=product.id,
        region_id=region.id,
        assigned_at=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        ended_at=None,
    )

    db_session.add(first_allocation)
    db_session.flush()

    second_allocation = QRAllocation(
        qr_code_id=qr_code.id,
        product_id=product.id,
        region_id=region.id,
        assigned_at=datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc),
        ended_at=None,
    )

    db_session.add(second_allocation)

    with pytest.raises(IntegrityError):
        db_session.flush()

@pytest.mark.integration
def test_active_qr_cannot_have_deactivated_at(db_session):
    """
    An ACTIVE QR code must have deactivated_at set to NULL.
    """

    _, _, qr_code = create_qr_dependencies(
        db_session,
        "ACTIVE-INVALID",
    )

    qr_code.status = "ACTIVE"
    qr_code.deactivated_at = datetime(
        2026, 1, 1, 12, 0, tzinfo=timezone.utc
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_inactive_qr_requires_deactivated_at(db_session):
    """
    An INACTIVE QR code must have a deactivation timestamp.
    """

    _, _, qr_code = create_qr_dependencies(
        db_session,
        "INACTIVE-INVALID",
    )

    qr_code.status = "INACTIVE"
    qr_code.deactivated_at = None

    with pytest.raises(IntegrityError):
        db_session.flush()

@pytest.mark.integration
def test_qr_batch_quantity_must_be_positive(db_session):
    """
    A QR batch cannot have zero or negative quantity.
    """

    product, region, _ = create_qr_dependencies(
        db_session,
        "INVALID-QUANTITY",
    )

    batch = QRBatch(
        batch_code="TEST-BATCH-ZERO",
        requested_product_id=product.id,
        requested_region_id=region.id,
        quantity=0,
    )

    db_session.add(batch)

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_qr_batch_rejects_invalid_generation_status(db_session):
    """
    A QR batch must use an allowed generation status.
    """

    product, region, _ = create_qr_dependencies(
        db_session,
        "INVALID-STATUS",
    )

    batch = QRBatch(
        batch_code="TEST-BATCH-INVALID-STATUS",
        requested_product_id=product.id,
        requested_region_id=region.id,
        quantity=1,
        generation_status="INVALID",
    )

    db_session.add(batch)

    with pytest.raises(IntegrityError):
        db_session.flush()