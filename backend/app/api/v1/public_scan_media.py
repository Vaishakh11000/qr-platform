from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.products import Product, ProductVersion
from app.models.scans import ScanEvent
from app.schemas.product_media import ProductMediaResponse
from app.services.media_service import (
    get_product_media,
    list_product_media,
    resolve_storage_path,
)


router = APIRouter(
    prefix="/public/scans/{scan_id}/media",
    tags=["Public Scan Media"],
)


def get_public_scan_context(
    db: Session,
    scan_id: UUID,
) -> tuple[ScanEvent, Product, ProductVersion]:
    """Return the exact product version associated with an allowed scan."""

    event = db.get(ScanEvent, scan_id)

    if (
        event is None
        or event.result_status != "ALLOWED"
        or event.completed_at is None
        or event.product_id is None
        or event.product_version_id is None
    ):
        raise HTTPException(status_code=404, detail="Media not found.")

    product = db.get(Product, event.product_id)

    if product is None or product.status != "ACTIVE":
        raise HTTPException(status_code=404, detail="Media not found.")

    version = db.get(ProductVersion, event.product_version_id)

    if (
        version is None
        or version.product_id != event.product_id
        or version.status not in ("PUBLISHED", "RETIRED")
    ):
        raise HTTPException(status_code=404, detail="Media not found.")

    return event, product, version


@router.get("", response_model=list[ProductMediaResponse])
def list_public_scan_media(
    scan_id: UUID,
    db: Session = Depends(get_db),
):
    event, _, _ = get_public_scan_context(db, scan_id)

    return list_product_media(
        db,
        event.product_id,
        version_id=event.product_version_id,
    )


@router.get("/{media_id}/file")
def download_public_scan_media(
    scan_id: UUID,
    media_id: UUID,
    db: Session = Depends(get_db),
):
    event, _, _ = get_public_scan_context(db, scan_id)

    media = get_product_media(
        db,
        event.product_id,
        media_id,
    )

    if media is None or media.version_id != event.product_version_id:
        raise HTTPException(status_code=404, detail="Media not found.")

    try:
        file_path = resolve_storage_path(media.storage_key)
    except ValueError:
        raise HTTPException(status_code=404, detail="Media not found.")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Media not found.")

    return FileResponse(
        path=file_path,
        filename=media.original_filename,
        media_type=media.mime_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )
