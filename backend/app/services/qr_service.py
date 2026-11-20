import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Product, QRAllocation, QRBatch, QRCode, Region
from app.services.audit_service import record_audit_event


MAX_BATCH_QUANTITY = 5000


class InvalidBatchQuantity(Exception):
    pass


class QRProductNotFound(Exception):
    pass


class QRProductArchived(Exception):
    pass


class QRRegionNotFound(Exception):
    pass


class QRRegionInactive(Exception):
    pass


class InvalidBatchAllocation(Exception):
    pass


class QRBatchConflict(Exception):
    pass


class QRBatchNotFound(Exception):
    pass


class QRBatchHasNoActiveCodes(Exception):
    pass


def generate_batch_code() -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = secrets.token_hex(5).upper()

    return f"QRB-{date_part}-{random_part}"


def generate_qr_token() -> str:
    return secrets.token_urlsafe(32)


def get_qr_destination(
    token: str,
    db: Session | None = None,
    *,
    public_base_url: str | None = None,
) -> str:
    from app.core.config import settings

    base_url = public_base_url or settings.public_base_url
    if db is not None and public_base_url is None:
        from app.services.system_setting_service import get_public_base_url

        base_url = get_public_base_url(db)
    base_url = base_url.rstrip("/")
    return f"{base_url}/q/{token}"


def generate_qr_batch(
    db: Session,
    *,
    quantity: int,
    batch_code: str | None = None,
    requested_product_id: UUID | None = None,
    requested_region_id: UUID | None = None,
    created_by: UUID | None = None,
) -> tuple[QRBatch, list[QRCode]]:
    if quantity < 1 or quantity > MAX_BATCH_QUANTITY:
        raise InvalidBatchQuantity()

    if (requested_product_id is None) != (requested_region_id is None):
        raise InvalidBatchAllocation()

    if requested_product_id is not None:
        product = db.get(Product, requested_product_id)

        if product is None:
            raise QRProductNotFound()

        if product.status == "ARCHIVED":
            raise QRProductArchived()

    if requested_region_id is not None:
        region = db.get(Region, requested_region_id)

        if region is None:
            raise QRRegionNotFound()

        if not region.is_active:
            raise QRRegionInactive()

    batch = QRBatch(
        batch_code=batch_code or generate_batch_code(),
        requested_product_id=requested_product_id,
        requested_region_id=requested_region_id,
        quantity=quantity,
        generation_status="PENDING",
        created_by=created_by,
    )

    try:
        db.add(batch)
        db.flush()

        qr_codes = [
            QRCode(
                batch_id=batch.id,
                token=generate_qr_token(),
            )
            for _ in range(quantity)
        ]

        db.add_all(qr_codes)
        db.flush()

        if requested_product_id is not None and requested_region_id is not None:
            assigned_at = datetime.now(timezone.utc)
            db.add_all([
                QRAllocation(
                    qr_code_id=code.id,
                    product_id=requested_product_id,
                    region_id=requested_region_id,
                    assigned_by=created_by,
                    assigned_at=assigned_at,
                    reason="Allocated during batch generation",
                )
                for code in qr_codes
            ])

        batch.generation_status = "GENERATED"
        batch.completed_at = datetime.now(timezone.utc)

        record_audit_event(
            db,
            admin_id=created_by,
            action="QR_BATCH_CREATED",
            entity_type="QR_BATCH",
            entity_id=batch.id,
            new_values={
                "batch_code": batch.batch_code,
                "quantity": batch.quantity,
                "requested_product_id": str(requested_product_id) if requested_product_id else None,
                "requested_region_id": str(requested_region_id) if requested_region_id else None,
                "generation_status": batch.generation_status,
            },
        )

        db.commit()
        db.refresh(batch)

        return batch, qr_codes

    except IntegrityError as exc:
        db.rollback()
        raise QRBatchConflict() from exc

    except Exception:
        db.rollback()
        raise


def list_qr_batches(
    db: Session,
    *,
    offset: int = 0,
    limit: int = 50,
) -> list[QRBatch]:
    query = (
        select(QRBatch)
        .order_by(QRBatch.created_at.desc(), QRBatch.id)
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(query).all())


def batch_allocation_summaries(
    db: Session,
    batch_ids: list[UUID],
) -> dict[UUID, dict[str, UUID | int | str | None]]:
    """Summarize current allocations for each active QR code in each batch."""
    if not batch_ids:
        return {}

    summaries: dict[UUID, dict] = {
        batch_id: {"active": 0, "allocated": 0, "pairs": set()}
        for batch_id in batch_ids
    }
    rows = db.execute(
        select(
            QRCode.batch_id,
            QRAllocation.product_id,
            QRAllocation.region_id,
        )
        .outerjoin(
            QRAllocation,
            and_(
                QRAllocation.qr_code_id == QRCode.id,
                QRAllocation.ended_at.is_(None),
            ),
        )
        .where(
            QRCode.batch_id.in_(batch_ids),
            QRCode.status == "ACTIVE",
        )
    ).all()

    for batch_id, product_id, region_id in rows:
        summary = summaries[batch_id]
        summary["active"] += 1
        if product_id is not None and region_id is not None:
            summary["allocated"] += 1
            summary["pairs"].add((product_id, region_id))

    result = {}
    for batch_id, summary in summaries.items():
        active = summary["active"]
        allocated = summary["allocated"]
        pairs = summary["pairs"]
        if active == 0:
            status = "NO_ACTIVE_CODES"
        elif allocated == 0:
            status = "UNALLOCATED"
        elif allocated != active or len(pairs) != 1:
            status = "MIXED"
        else:
            status = "ALLOCATED"

        product_id, region_id = next(iter(pairs)) if status == "ALLOCATED" else (None, None)
        result[batch_id] = {
            "current_product_id": product_id,
            "current_region_id": region_id,
            "allocation_status": status,
            "active_code_count": active,
            "allocated_code_count": allocated,
        }

    return result


def get_qr_batch(
    db: Session,
    batch_id: UUID,
) -> QRBatch | None:
    return db.get(QRBatch, batch_id)


def retire_qr_batch(
    db: Session,
    batch_id: UUID,
    *,
    admin_id: UUID | None = None,
) -> tuple[QRBatch, int]:
    batch = db.scalar(
        select(QRBatch).where(QRBatch.id == batch_id).with_for_update()
    )
    if batch is None:
        raise QRBatchNotFound()

    if batch.retired_at is not None:
        return batch, 0

    now = datetime.now(timezone.utc)
    codes = list(db.scalars(
        select(QRCode)
        .where(QRCode.batch_id == batch_id, QRCode.status == "ACTIVE")
        .order_by(QRCode.id)
        .with_for_update()
    ).all())

    try:
        batch.retired_at = now
        if codes:
            code_ids = [code.id for code in codes]
            allocations = list(db.scalars(
                select(QRAllocation)
                .where(
                    QRAllocation.qr_code_id.in_(code_ids),
                    QRAllocation.ended_at.is_(None),
                )
                .with_for_update()
            ).all())
            for allocation in allocations:
                allocation.ended_at = max(
                    now,
                    allocation.assigned_at + timedelta(microseconds=1),
                )

            for code in codes:
                code.status = "REVOKED"
                code.deactivated_at = now

        record_audit_event(
            db,
            admin_id=admin_id,
            action="QR_BATCH_RETIRED",
            entity_type="QR_BATCH",
            entity_id=batch.id,
            old_values={"active_code_count": len(codes), "retired_at": None},
            new_values={"revoked_code_count": len(codes), "retired_at": now.isoformat()},
        )
        db.commit()
        db.refresh(batch)
        return batch, len(codes)
    except Exception:
        db.rollback()
        raise


def allocate_qr_batch(
    db: Session,
    batch_id: UUID,
    *,
    product_id: UUID,
    region_id: UUID,
    reason: str | None = None,
    admin_id: UUID | None = None,
) -> dict[str, int | str | UUID]:
    batch = db.scalar(
        select(QRBatch).where(QRBatch.id == batch_id).with_for_update()
    )
    if batch is None:
        raise QRBatchNotFound()

    product = db.get(Product, product_id)
    if product is None:
        raise QRProductNotFound()
    if product.status == "ARCHIVED":
        raise QRProductArchived()

    region = db.get(Region, region_id)
    if region is None:
        raise QRRegionNotFound()
    if not region.is_active:
        raise QRRegionInactive()

    codes = list(db.scalars(
        select(QRCode)
        .where(QRCode.batch_id == batch_id, QRCode.status == "ACTIVE")
        .order_by(QRCode.id)
        .with_for_update()
    ).all())
    if not codes:
        raise QRBatchHasNoActiveCodes()

    try:
        allocations = list(db.scalars(
            select(QRAllocation)
            .where(
                QRAllocation.qr_code_id.in_([code.id for code in codes]),
                QRAllocation.ended_at.is_(None),
            )
            .with_for_update()
        ).all())
        active_by_code = {allocation.qr_code_id: allocation for allocation in allocations}
        old_pairs = {
            (str(allocation.product_id), str(allocation.region_id))
            for allocation in allocations
        }
        now = datetime.now(timezone.utc)
        new_allocations = []
        reassigned_count = 0
        unchanged_count = 0

        for code in codes:
            current = active_by_code.get(code.id)
            if current is not None and current.product_id == product_id and current.region_id == region_id:
                unchanged_count += 1
                continue
            assigned_at = now
            if current is not None:
                assigned_at = max(now, current.assigned_at + timedelta(microseconds=1))
                current.ended_at = assigned_at
                reassigned_count += 1
            new_allocations.append(QRAllocation(
                qr_code_id=code.id,
                product_id=product_id,
                region_id=region_id,
                assigned_by=admin_id,
                assigned_at=assigned_at,
                reason=reason,
            ))

        db.add_all(new_allocations)
        if new_allocations:
            record_audit_event(
                db,
                admin_id=admin_id,
                action="QR_BATCH_ALLOCATED",
                entity_type="QR_BATCH",
                entity_id=batch.id,
                old_values={"allocations": [
                    {"product_id": pair[0], "region_id": pair[1]}
                    for pair in sorted(old_pairs)
                ]},
                new_values={
                    "product_id": str(product_id),
                    "region_id": str(region_id),
                    "active_code_count": len(codes),
                    "allocated_count": len(new_allocations),
                    "reassigned_count": reassigned_count,
                    "unchanged_count": unchanged_count,
                    "reason": reason,
                },
            )
        db.commit()
        return {
            "batch_id": batch.id,
            "batch_code": batch.batch_code,
            "active_code_count": len(codes),
            "allocated_count": len(new_allocations) - reassigned_count,
            "reassigned_count": reassigned_count,
            "unchanged_count": unchanged_count,
        }
    except Exception:
        db.rollback()
        raise


def list_batch_qr_codes(
    db: Session,
    batch_id: UUID,
    *,
    offset: int = 0,
    limit: int = 100,
) -> list[QRCode]:
    query = (
        select(QRCode)
        .where(QRCode.batch_id == batch_id)
        .order_by(QRCode.created_at, QRCode.id)
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(query).all())
