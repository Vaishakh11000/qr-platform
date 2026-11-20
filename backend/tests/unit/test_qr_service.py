from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models import Product, QRAllocation, QRBatch, QRCode, Region
from app.services.qr_service import (
    InvalidBatchQuantity,
    QRBatchConflict,
    QRProductArchived,
    QRProductNotFound,
    QRRegionInactive,
    QRRegionNotFound,
    generate_qr_batch,
    get_qr_destination,
)


def create_product(db_session, status="DRAFT"):
    suffix = uuid4().hex[:12]

    product = Product(
        sku=f"QR-TEST-{suffix}",
        name=f"QR Test Product {suffix}",
        status=status,
    )

    db_session.add(product)
    db_session.flush()

    return product


def create_region(db_session, is_active=True):
    suffix = uuid4().hex[:12]

    region = Region(
        name=f"QR Test Region {suffix}",
        region_code=f"QR-REGION-{suffix}",
        region_type="TEST",
        is_active=is_active,
    )

    db_session.add(region)
    db_session.flush()

    return region


@pytest.mark.unit
def test_generate_qr_batch_creates_requested_quantity(db_session):
    batch, codes = generate_qr_batch(
        db_session,
        quantity=10,
    )

    assert batch.quantity == 10
    assert batch.generation_status == "GENERATED"
    assert batch.completed_at is not None
    assert batch.batch_code.startswith("QRB-")

    assert len(codes) == 10
    assert all(code.batch_id == batch.id for code in codes)
    assert all(code.status == "ACTIVE" for code in codes)
    assert all(len(code.token) == 43 for code in codes)

    tokens = [code.token for code in codes]
    assert len(set(tokens)) == 10


@pytest.mark.unit
def test_generate_qr_batch_with_product_and_region(db_session):
    product = create_product(db_session)
    region = create_region(db_session)

    batch, codes = generate_qr_batch(
        db_session,
        quantity=3,
        requested_product_id=product.id,
        requested_region_id=region.id,
    )

    assert batch.requested_product_id == product.id
    assert batch.requested_region_id == region.id
    assert len(codes) == 3
    allocations = db_session.scalars(
        select(QRAllocation).where(
            QRAllocation.qr_code_id.in_([code.id for code in codes]),
            QRAllocation.ended_at.is_(None),
        )
    ).all()
    assert len(allocations) == 3
    assert {allocation.product_id for allocation in allocations} == {product.id}
    assert {allocation.region_id for allocation in allocations} == {region.id}


@pytest.mark.unit
@pytest.mark.parametrize("quantity", [0, -1, 5001])
def test_invalid_batch_quantity_is_rejected(db_session, quantity):
    with pytest.raises(InvalidBatchQuantity):
        generate_qr_batch(
            db_session,
            quantity=quantity,
        )


@pytest.mark.unit
def test_generate_batch_rejects_nonexistent_product(db_session):
    with pytest.raises(QRProductNotFound):
        generate_qr_batch(
            db_session,
            quantity=1,
            requested_product_id=uuid4(),
            requested_region_id=uuid4(),
        )


@pytest.mark.unit
def test_generate_batch_rejects_archived_product(db_session):
    product = create_product(db_session, status="ARCHIVED")

    with pytest.raises(QRProductArchived):
        generate_qr_batch(
            db_session,
            quantity=1,
            requested_product_id=product.id,
            requested_region_id=uuid4(),
        )


@pytest.mark.unit
def test_generate_batch_rejects_nonexistent_region(db_session):
    product = create_product(db_session)
    with pytest.raises(QRRegionNotFound):
        generate_qr_batch(
            db_session,
            quantity=1,
            requested_product_id=product.id,
            requested_region_id=uuid4(),
        )


@pytest.mark.unit
def test_generate_batch_rejects_inactive_region(db_session):
    product = create_product(db_session)
    region = create_region(db_session, is_active=False)

    with pytest.raises(QRRegionInactive):
        generate_qr_batch(
            db_session,
            quantity=1,
            requested_product_id=product.id,
            requested_region_id=region.id,
        )


@pytest.mark.unit
def test_duplicate_batch_code_is_rejected(db_session):
    generate_qr_batch(
        db_session,
        quantity=1,
        batch_code="QR-DUPLICATE-TEST",
    )

    with pytest.raises(QRBatchConflict):
        generate_qr_batch(
            db_session,
            quantity=1,
            batch_code="QR-DUPLICATE-TEST",
        )


@pytest.mark.unit
def test_qr_destination_uses_configured_base_url():
    from app.core.config import settings

    destination = get_qr_destination("sample-token")

    assert destination.endswith("/q/sample-token")
    assert destination.startswith(settings.public_base_url.rstrip("/"))


@pytest.mark.unit
def test_generated_codes_are_saved_in_database(db_session):
    batch, codes = generate_qr_batch(
        db_session,
        quantity=5,
    )

    stored_count = db_session.scalar(
        select(func.count())
        .select_from(QRCode)
        .where(QRCode.batch_id == batch.id)
    )

    assert stored_count == 5

    stored_batch = db_session.get(QRBatch, batch.id)
    assert stored_batch is not None
    assert stored_batch.generation_status == "GENERATED"
