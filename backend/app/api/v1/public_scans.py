from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Product, ProductVersion
from app.schemas.public_scan import (
    ScanCompletionResponse,
    ScanLocationSubmission,
    ScanProductResponse,
    ScanStartRequest,
    ScanStartResponse,
)
from app.services.scan_service import (
    ProductUnavailable,
    PublishedVersionUnavailable,
    QRCodeInactive,
    QRCodeUnallocated,
    QRTokenNotFound,
    ScanAlreadyCompleted,
    ScanEventNotFound,
    InvalidScanLocation,
    begin_scan,
    complete_scan,
)


router = APIRouter(
    prefix="/public/scans",
    tags=["Public QR Scanning"],
)


_PRIVATE_SNAPSHOT_FIELDS = frozenset({
    "example",
    "data_quality_note",
    "internal_review_note",
})


def public_content_snapshot(value: Any) -> Any:
    """Remove source-review fields before product content leaves the API."""
    if isinstance(value, dict):
        return {
            key: public_content_snapshot(item)
            for key, item in value.items()
            if not isinstance(key, str) or key.casefold() not in _PRIVATE_SNAPSHOT_FIELDS
        }
    if isinstance(value, list):
        return [public_content_snapshot(item) for item in value]
    return value


@router.post(
    "/start",
    response_model=ScanStartResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_public_scan(
    scan_data: ScanStartRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        result = begin_scan(
            db,
            scan_data.token,
            user_agent=request.headers.get("user-agent"),
        )

        policy = result.location_policy

        return ScanStartResponse(
            scan_id=result.event.id,
            location_requested=policy is not None,
            location_requirement=policy.requirement if policy else None,
            location_method=policy.method if policy else None,
        )

    except QRTokenNotFound:
        raise HTTPException(
            status_code=404,
            detail="This QR code does not exist.",
        )

    except QRCodeInactive:
        raise HTTPException(
            status_code=409,
            detail="This QR code is no longer active.",
        )

    except QRCodeUnallocated:
        raise HTTPException(
            status_code=409,
            detail="This QR code has not been assigned to a product.",
        )

    except ProductUnavailable:
        raise HTTPException(
            status_code=409,
            detail="This product is not currently available.",
        )

    except PublishedVersionUnavailable:
        raise HTTPException(
            status_code=409,
            detail="Published product information is unavailable.",
        )


@router.post(
    "/{scan_id}/location",
    response_model=ScanCompletionResponse,
)
def submit_scan_location(
    scan_id: UUID,
    location_data: ScanLocationSubmission,
    db: Session = Depends(get_db),
):
    try:
        event, message = complete_scan(
            db,
            scan_id,
            location_data,
        )

    except ScanEventNotFound:
        raise HTTPException(
            status_code=404,
            detail="Scan session not found.",
        )

    except ScanAlreadyCompleted:
        raise HTTPException(
            status_code=409,
            detail="This scan session has already been completed.",
        )

    except InvalidScanLocation:
        raise HTTPException(
            status_code=422,
            detail="The submitted location is not permitted by this policy.",
        )

    product_response = None

    if event.result_status == "ALLOWED":
        product = db.get(Product, event.product_id)
        version = db.get(ProductVersion, event.product_version_id)

        if (
            product is not None
            and product.status == "ACTIVE"
            and version is not None
            and version.status in ("PUBLISHED", "RETIRED")
        ):
            product_response = ScanProductResponse(
                id=product.id,
                version_id=version.id,
                version_number=version.version_number,
                sku=product.sku,
                name=product.name,
                content_snapshot=public_content_snapshot(version.content_snapshot),
            )

    return ScanCompletionResponse(
        scan_id=event.id,
        result_status=event.result_status,
        location_status=event.location_status,
        message=message,
        product=product_response,
    )
