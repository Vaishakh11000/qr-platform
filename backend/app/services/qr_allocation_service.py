from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Product, Region, QRCode, QRAllocation
from app.services.audit_service import record_audit_event


MAX_ALLOCATION_QUANTITY = 5000


class AllocationError(Exception):
    pass


class AllocationProductNotFound(AllocationError):
    pass


class AllocationProductArchived(AllocationError):
    pass


class AllocationRegionNotFound(AllocationError):
    pass


class AllocationRegionInactive(AllocationError):
    pass


class AllocationQRCodeNotFound(AllocationError):
    pass


class AllocationQRCodeInactive(AllocationError):
    pass


class QRAlreadyAllocated(AllocationError):
    pass


class AllocationConflict(AllocationError):
    pass


class InvalidAllocationRequest(AllocationError):
    pass


def allocate_qr_codes(
    db: Session,
    *,
    qr_code_ids: list[UUID],
    product_id: UUID,
    region_id: UUID,
    assigned_by: UUID | None = None,
    reason: str | None = None,
) -> list[QRAllocation]:
    """
    Allocate multiple QR codes to one product and region atomically.

    Either every requested QR code is allocated, or none are.
    Existing allocations are never overwritten or deleted.
    """

    if not qr_code_ids or len(qr_code_ids) > MAX_ALLOCATION_QUANTITY:
        raise InvalidAllocationRequest()

    if len(set(qr_code_ids)) != len(qr_code_ids):
        raise InvalidAllocationRequest()

    try:
        product = db.get(Product, product_id)

        if product is None:
            raise AllocationProductNotFound()

        if product.status == "ARCHIVED":
            raise AllocationProductArchived()

        region = db.get(Region, region_id)

        if region is None:
            raise AllocationRegionNotFound()

        if not region.is_active:
            raise AllocationRegionInactive()

        # Lock QR rows in a consistent order to reduce concurrent
        # allocation conflicts.
        qr_codes = list(
            db.scalars(
                select(QRCode)
                .where(QRCode.id.in_(qr_code_ids))
                .order_by(QRCode.id)
                .with_for_update()
            ).all()
        )

        found_ids = {code.id for code in qr_codes}
        missing_ids = set(qr_code_ids) - found_ids

        if missing_ids:
            raise AllocationQRCodeNotFound()

        if any(code.status != "ACTIVE" for code in qr_codes):
            raise AllocationQRCodeInactive()

        existing_allocations = set(
            db.scalars(
                select(QRAllocation.qr_code_id).where(
                    QRAllocation.qr_code_id.in_(qr_code_ids),
                    QRAllocation.ended_at.is_(None),
                )
            ).all()
        )

        if existing_allocations:
            raise QRAlreadyAllocated()

        assigned_at = datetime.now(timezone.utc)

        allocations = [
            QRAllocation(
                qr_code_id=code.id,
                product_id=product_id,
                region_id=region_id,
                assigned_by=assigned_by,
                assigned_at=assigned_at,
                reason=reason,
            )
            for code in qr_codes
        ]

        db.add_all(allocations)
        db.flush()
        record_audit_event(
            db,
            admin_id=assigned_by,
            action="QR_CODES_ALLOCATED",
            entity_type="QR_ALLOCATION",
            entity_id=allocations[0].id,
            new_values={
                "qr_code_count": len(allocations),
                "qr_code_ids_sample": [str(code.id) for code in qr_codes[:20]],
                "product_id": str(product_id),
                "region_id": str(region_id),
                "reason": reason,
            },
        )
        db.commit()

        for allocation in allocations:
            db.refresh(allocation)

        return allocations

    except AllocationError:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()
        raise AllocationConflict() from exc

    except Exception:
        db.rollback()
        raise


def get_active_qr_allocation(
    db: Session,
    qr_code_id: UUID,
) -> QRAllocation | None:
    return db.scalar(
        select(QRAllocation).where(
            QRAllocation.qr_code_id == qr_code_id,
            QRAllocation.ended_at.is_(None),
        )
    )


def list_qr_allocation_history(
    db: Session,
    qr_code_id: UUID,
    *,
    offset: int = 0,
    limit: int = 100,
) -> list[QRAllocation]:
    return list(
        db.scalars(
            select(QRAllocation)
            .where(QRAllocation.qr_code_id == qr_code_id)
            .order_by(
                QRAllocation.assigned_at.desc(),
                QRAllocation.id,
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )


class QRCodeNotFound(AllocationError):
    pass


class QRCodeInactive(AllocationError):
    pass


class QRNotAllocated(AllocationError):
    pass


class AllocationUnchanged(AllocationError):
    pass


def reassign_qr_code(
    db: Session,
    *,
    qr_code_id: UUID,
    product_id: UUID,
    region_id: UUID,
    assigned_by: UUID | None = None,
    reason: str | None = None,
) -> QRAllocation:
    """
    End the current allocation and create a new one atomically.

    The previous allocation is retained as historical data.
    The old and new allocation periods meet at the same timestamp.
    """

    try:
        qr_code = db.scalar(
            select(QRCode)
            .where(QRCode.id == qr_code_id)
            .with_for_update()
        )

        if qr_code is None:
            raise QRCodeNotFound()

        if qr_code.status != "ACTIVE":
            raise QRCodeInactive()

        product = db.get(Product, product_id)

        if product is None:
            raise AllocationProductNotFound()

        if product.status == "ARCHIVED":
            raise AllocationProductArchived()

        region = db.get(Region, region_id)

        if region is None:
            raise AllocationRegionNotFound()

        if not region.is_active:
            raise AllocationRegionInactive()

        current_allocation = db.scalar(
            select(QRAllocation)
            .where(
                QRAllocation.qr_code_id == qr_code_id,
                QRAllocation.ended_at.is_(None),
            )
            .with_for_update()
        )

        if current_allocation is None:
            raise QRNotAllocated()

        if (
            current_allocation.product_id == product_id
            and current_allocation.region_id == region_id
        ):
            raise AllocationUnchanged()

        old_values = {
            "product_id": str(current_allocation.product_id),
            "region_id": str(current_allocation.region_id),
            "reason": current_allocation.reason,
        }

        transition_time = datetime.now(timezone.utc)

        if transition_time <= current_allocation.assigned_at:
            raise AllocationConflict()

        current_allocation.ended_at = transition_time

        # Release the active-allocation index and close the old
        # time range before inserting the replacement allocation.
        db.flush()

        new_allocation = QRAllocation(
            qr_code_id=qr_code_id,
            product_id=product_id,
            region_id=region_id,
            assigned_by=assigned_by,
            assigned_at=transition_time,
            reason=reason,
        )

        db.add(new_allocation)
        db.flush()
        record_audit_event(
            db,
            admin_id=assigned_by,
            action="QR_CODE_REASSIGNED",
            entity_type="QR_CODE",
            entity_id=qr_code_id,
            old_values=old_values,
            new_values={
                "product_id": str(product_id),
                "region_id": str(region_id),
                "reason": reason,
            },
        )
        db.commit()
        db.refresh(new_allocation)

        return new_allocation

    except AllocationError:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()
        raise AllocationConflict() from exc

    except Exception:
        db.rollback()
        raise


class QRCodeNotFound(AllocationError):
    pass


class QRCodeInactive(AllocationError):
    pass


class QRNotAllocated(AllocationError):
    pass


class AllocationUnchanged(AllocationError):
    pass


