from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import require_super_admin
from app.core.database import get_db
from app.models import AdminUser
from app.models import QRCode
from app.schemas.qr_allocation import (
    QRBatchAllocationRequest,
    QRBatchAllocationResponse,
    QRAllocationCreate,
    QRAllocationReassign,
    QRAllocationResponse,
)
from app.services.qr_allocation_service import (
    AllocationConflict,
    AllocationProductArchived,
    AllocationProductNotFound,
    AllocationQRCodeInactive,
    AllocationQRCodeNotFound,
    AllocationRegionInactive,
    AllocationRegionNotFound,
    InvalidAllocationRequest,
    QRAlreadyAllocated,
    AllocationUnchanged,
    QRCodeInactive,
    QRCodeNotFound,
    QRNotAllocated,
    reassign_qr_code,
    allocate_qr_codes,
    get_active_qr_allocation,
    list_qr_allocation_history,
)
from app.services.qr_service import (
    QRBatchHasNoActiveCodes,
    QRBatchNotFound,
    QRProductArchived,
    QRProductNotFound,
    QRRegionInactive,
    QRRegionNotFound,
    allocate_qr_batch,
)


router = APIRouter(
    prefix="/qr",
    tags=["QR Allocations"],
    dependencies=[Depends(require_super_admin)],
)


@router.put(
    "/batches/{batch_id}/allocation",
    response_model=QRBatchAllocationResponse,
)
def allocate_or_reassign_qr_batch_endpoint(
    batch_id: UUID,
    allocation_data: QRBatchAllocationRequest,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return allocate_qr_batch(
            db,
            batch_id,
            product_id=allocation_data.product_id,
            region_id=allocation_data.region_id,
            reason=allocation_data.reason,
            admin_id=actor.id,
        )
    except QRBatchNotFound:
        raise HTTPException(status_code=404, detail="QR batch not found.")
    except QRBatchHasNoActiveCodes:
        raise HTTPException(status_code=409, detail="QR batch has no active codes to allocate.")
    except QRProductNotFound:
        raise HTTPException(status_code=404, detail="Product not found.")
    except QRProductArchived:
        raise HTTPException(status_code=409, detail="Cannot allocate QR codes to an archived product.")
    except QRRegionNotFound:
        raise HTTPException(status_code=404, detail="Region not found.")
    except QRRegionInactive:
        raise HTTPException(status_code=409, detail="Cannot allocate QR codes to an inactive region.")


@router.post(
    "/allocations",
    response_model=list[QRAllocationResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_qr_allocations_endpoint(
    allocation_data: QRAllocationCreate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return allocate_qr_codes(
            db,
            qr_code_ids=allocation_data.qr_code_ids,
            product_id=allocation_data.product_id,
            region_id=allocation_data.region_id,
            assigned_by=actor.id,
            reason=allocation_data.reason,
        )

    except InvalidAllocationRequest:
        raise HTTPException(
            status_code=422,
            detail="Invalid allocation request.",
        )

    except AllocationProductNotFound:
        raise HTTPException(
            status_code=404,
            detail="Product not found.",
        )

    except AllocationProductArchived:
        raise HTTPException(
            status_code=409,
            detail="Cannot allocate QR codes to an archived product.",
        )

    except AllocationRegionNotFound:
        raise HTTPException(
            status_code=404,
            detail="Region not found.",
        )

    except AllocationRegionInactive:
        raise HTTPException(
            status_code=409,
            detail="Cannot allocate QR codes to an inactive region.",
        )

    except AllocationQRCodeNotFound:
        raise HTTPException(
            status_code=404,
            detail="One or more QR codes were not found.",
        )

    except AllocationQRCodeInactive:
        raise HTTPException(
            status_code=409,
            detail="One or more QR codes are inactive or revoked.",
        )

    except QRAlreadyAllocated:
        raise HTTPException(
            status_code=409,
            detail="One or more QR codes already have active allocations.",
        )

    except AllocationConflict:
        raise HTTPException(
            status_code=409,
            detail="Allocation conflict. No QR codes were allocated.",
        )


@router.get(
    "/codes/{qr_code_id}/allocation",
    response_model=QRAllocationResponse | None,
)
def get_active_qr_allocation_endpoint(
    qr_code_id: UUID,
    db: Session = Depends(get_db),
):
    qr_code = db.get(QRCode, qr_code_id)

    if qr_code is None:
        raise HTTPException(
            status_code=404,
            detail="QR code not found.",
        )

    return get_active_qr_allocation(db, qr_code_id)


@router.get(
    "/codes/{qr_code_id}/allocation/history",
    response_model=list[QRAllocationResponse],
)
def get_qr_allocation_history_endpoint(
    qr_code_id: UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    qr_code = db.get(QRCode, qr_code_id)

    if qr_code is None:
        raise HTTPException(
            status_code=404,
            detail="QR code not found.",
        )

    return list_qr_allocation_history(
        db,
        qr_code_id,
        offset=offset,
        limit=limit,
    )


@router.put(
    "/codes/{qr_code_id}/allocation",
    response_model=QRAllocationResponse,
)
def reassign_qr_allocation_endpoint(
    qr_code_id: UUID,
    allocation_data: QRAllocationReassign,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return reassign_qr_code(
            db,
            qr_code_id=qr_code_id,
            product_id=allocation_data.product_id,
            region_id=allocation_data.region_id,
            assigned_by=actor.id,
            reason=allocation_data.reason,
        )

    except QRCodeNotFound:
        raise HTTPException(
            status_code=404,
            detail="QR code not found.",
        )

    except QRCodeInactive:
        raise HTTPException(
            status_code=409,
            detail="Cannot reassign an inactive or revoked QR code.",
        )

    except QRNotAllocated:
        raise HTTPException(
            status_code=409,
            detail="QR code has no active allocation to reassign.",
        )

    except AllocationUnchanged:
        raise HTTPException(
            status_code=409,
            detail="QR code is already allocated to this product and region.",
        )

    except AllocationProductNotFound:
        raise HTTPException(
            status_code=404,
            detail="Product not found.",
        )

    except AllocationProductArchived:
        raise HTTPException(
            status_code=409,
            detail="Cannot allocate QR codes to an archived product.",
        )

    except AllocationRegionNotFound:
        raise HTTPException(
            status_code=404,
            detail="Region not found.",
        )

    except AllocationRegionInactive:
        raise HTTPException(
            status_code=409,
            detail="Cannot allocate QR codes to an inactive region.",
        )

    except AllocationConflict:
        raise HTTPException(
            status_code=409,
            detail="Allocation conflict. The previous allocation was preserved.",
        )
