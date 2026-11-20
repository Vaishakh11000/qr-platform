import csv
import io
import re
import zipfile
from io import BytesIO
from math import ceil
from typing import Literal
from uuid import UUID

import segno
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.auth import require_super_admin
from app.core.database import get_db
from app.models import AdminUser, Product, QRAllocation, QRCode, Region
from app.schemas.qr import QRBatchCreate, QRBatchResponse, QRBatchRetireResponse, QRCodeResponse
from app.services.qr_service import (
    InvalidBatchQuantity,
    InvalidBatchAllocation,
    QRBatchConflict,
    QRBatchNotFound,
    QRProductArchived,
    QRProductNotFound,
    QRRegionInactive,
    QRRegionNotFound,
    generate_qr_batch,
    get_qr_batch,
    get_qr_destination,
    list_batch_qr_codes,
    list_qr_batches,
    batch_allocation_summaries,
    retire_qr_batch,
)
from app.services.system_setting_service import get_public_base_url


def _safe_csv_value(value):
    if isinstance(value, str) and re.match(r"^\s*[=+\-@]", value):
        return f"'{value}"
    return value


router = APIRouter(
    prefix="/qr",
    tags=["QR Management"],
    dependencies=[Depends(require_super_admin)],
)


@router.post(
    "/batches",
    response_model=QRBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_qr_batch_endpoint(
    batch_data: QRBatchCreate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        batch, _ = generate_qr_batch(
            db,
            quantity=batch_data.quantity,
            batch_code=batch_data.batch_code,
            requested_product_id=batch_data.requested_product_id,
            requested_region_id=batch_data.requested_region_id,
            created_by=actor.id,
        )
        summary = batch_allocation_summaries(db, [batch.id])[batch.id]
        return QRBatchResponse.model_validate(batch).model_copy(update=summary)

    except InvalidBatchQuantity:
        raise HTTPException(
            status_code=422,
            detail="Batch quantity must be between 1 and 5000.",
        )

    except InvalidBatchAllocation:
        raise HTTPException(
            status_code=422,
            detail="Select both a product and region to allocate codes during generation.",
        )

    except QRProductNotFound:
        raise HTTPException(
            status_code=404,
            detail="Requested product not found.",
        )

    except QRProductArchived:
        raise HTTPException(
            status_code=409,
            detail="Cannot generate a batch for an archived product.",
        )

    except QRRegionNotFound:
        raise HTTPException(
            status_code=404,
            detail="Requested region not found.",
        )

    except QRRegionInactive:
        raise HTTPException(
            status_code=409,
            detail="Cannot generate a batch for an inactive region.",
        )

    except QRBatchConflict:
        raise HTTPException(
            status_code=409,
            detail="Batch code already exists or the batch could not be generated.",
        )


@router.get(
    "/batches",
    response_model=list[QRBatchResponse],
)
def list_qr_batches_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    batches = list_qr_batches(
        db,
        offset=offset,
        limit=limit,
    )
    summaries = batch_allocation_summaries(db, [batch.id for batch in batches])
    return [
        QRBatchResponse.model_validate(batch).model_copy(update=summaries[batch.id])
        for batch in batches
    ]


@router.get(
    "/batches/{batch_id}",
    response_model=QRBatchResponse,
)
def get_qr_batch_endpoint(
    batch_id: UUID,
    db: Session = Depends(get_db),
):
    batch = get_qr_batch(db, batch_id)

    if batch is None:
        raise HTTPException(
            status_code=404,
            detail="QR batch not found.",
        )

    summary = batch_allocation_summaries(db, [batch.id])[batch.id]
    return QRBatchResponse.model_validate(batch).model_copy(update=summary)


def _make_batch_pdf(batch, codes, public_base_url: str) -> BytesIO:
    page_width, page_height = 1275, 1650
    columns, rows = 3, 4
    qr_size = 300
    per_page = columns * rows
    page_count = ceil(len(codes) / per_page)
    pages = []

    for page_index in range(page_count):
        page = Image.new("1", (page_width, page_height), color=1)
        draw = ImageDraw.Draw(page)
        draw.text((56, 36), f"QR BATCH  {batch.batch_code}", fill=0)
        draw.text((56, 62), f"Active codes  {len(codes)}", fill=0)

        for cell_index, code in enumerate(codes[page_index * per_page:(page_index + 1) * per_page]):
            index = page_index * per_page + cell_index + 1
            column = cell_index % columns
            row = cell_index // columns
            cell_width = page_width // columns
            cell_height = 375
            cell_x = column * cell_width
            cell_y = 105 + row * cell_height

            scan_url = get_qr_destination(code.token, public_base_url=public_base_url)
            qr = segno.make(scan_url, error="H")
            png = BytesIO()
            qr.save(png, kind="png", scale=8, border=4)
            png.seek(0)
            with Image.open(png) as source:
                qr_image = source.convert("1").resize(
                    (qr_size, qr_size), Image.Resampling.NEAREST
                )
            x = cell_x + (cell_width - qr_size) // 2
            y = cell_y + 10
            page.paste(qr_image, (x, y))
            draw.text((cell_x + 24, y + qr_size + 12), f"QR {index:04d}  {code.token[-8:]}", fill=0)

        draw.text((page_width - 120, page_height - 36), f"{page_index + 1}/{page_count}", fill=0)
        pages.append(page)

    output = BytesIO()
    pages[0].save(
        output,
        format="PDF",
        save_all=True,
        append_images=pages[1:],
        resolution=150.0,
    )
    output.seek(0)
    return output


@router.get("/batches/{batch_id}/share")
def share_qr_batch_endpoint(
    batch_id: UUID,
    export_format: Literal["svg-zip", "pdf", "png-zip"] = Query(
        default="svg-zip",
        alias="format",
    ),
    db: Session = Depends(get_db),
):
    batch = get_qr_batch(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="QR batch not found.")

    codes = [
        code
        for code in list_batch_qr_codes(db, batch_id, offset=0, limit=5000)
        if code.status == "ACTIVE"
    ]
    if not codes:
        raise HTTPException(
            status_code=409,
            detail="This batch has no active QR codes to share.",
        )

    current_allocations = db.execute(
        select(
            QRAllocation.qr_code_id,
            Product.name.label("product_name"),
            Product.sku.label("product_sku"),
            Region.name.label("region_name"),
            Region.region_code.label("region_code"),
        )
        .join(Product, Product.id == QRAllocation.product_id)
        .join(Region, Region.id == QRAllocation.region_id)
        .where(
            QRAllocation.qr_code_id.in_([code.id for code in codes]),
            QRAllocation.ended_at.is_(None),
        )
    ).all()
    allocation_by_code = {
        row.qr_code_id: {
            "product_name": row.product_name,
            "product_sku": row.product_sku,
            "region_name": row.region_name,
            "region_code": row.region_code,
        }
        for row in current_allocations
    }

    safe_batch_code = re.sub(r"[^A-Za-z0-9_-]+", "-", batch.batch_code).strip("-") or "qr-batch"
    public_base_url = get_public_base_url(db)
    if export_format == "pdf":
        pdf = _make_batch_pdf(batch, codes, public_base_url)
        return StreamingResponse(
            pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_batch_code}-qr-codes.pdf"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    archive = BytesIO()
    folder = "png" if export_format == "png-zip" else "svg"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        csv_file = io.StringIO(newline="")
        writer = csv.writer(csv_file)
        writer.writerow([
            "number", "qr_file", "token", "scan_url", "status",
            "product_name", "product_sku", "region_name", "region_code",
        ])

        for index, code in enumerate(codes, start=1):
            extension = "png" if export_format == "png-zip" else "svg"
            filename = f"{safe_batch_code}/{folder}/qr-{index:04d}-{str(code.id)[:8]}.{extension}"
            scan_url = get_qr_destination(code.token, public_base_url=public_base_url)
            image = segno.make(scan_url, error="H")
            image_file = BytesIO()
            image.save(image_file, kind=extension, scale=8, border=4)
            bundle.writestr(filename, image_file.getvalue())
            allocation = allocation_by_code.get(code.id, {})
            writer.writerow([_safe_csv_value(value) for value in [
                index,
                filename,
                code.token,
                scan_url,
                code.status,
                allocation.get("product_name", ""),
                allocation.get("product_sku", ""),
                allocation.get("region_name", ""),
                allocation.get("region_code", ""),
            ]])

        bundle.writestr(f"{safe_batch_code}/scan-links.csv", csv_file.getvalue().encode("utf-8-sig"))
        bundle.writestr(
            f"{safe_batch_code}/README.txt",
            (
                f"QR batch: {batch.batch_code}\n"
                f"Active QR codes included: {len(codes)}\n\n"
                "The CSV contains each QR token, scan URL, and current product/region allocation when assigned. "
                "QR access still follows the current "
                "product allocation, publication status, and location policy. Scan URLs use the "
                "configured public base URL; confirm that recipients can reach it before distributing.\n"
            ),
        )

    archive.seek(0)
    zip_suffix = "pngs" if export_format == "png-zip" else "svgs"
    return StreamingResponse(
        archive,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_batch_code}-{zip_suffix}.zip"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/batches/{batch_id}/retire",
    response_model=QRBatchRetireResponse,
)
def retire_qr_batch_endpoint(
    batch_id: UUID,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        batch, revoked_count = retire_qr_batch(db, batch_id, admin_id=actor.id)
    except QRBatchNotFound:
        raise HTTPException(
            status_code=404,
            detail="QR batch not found.",
        )
    return {
        "batch_id": batch.id,
        "batch_code": batch.batch_code,
        "revoked_count": revoked_count,
        "retired_at": batch.retired_at,
    }


@router.get(
    "/batches/{batch_id}/codes",
)
def list_batch_qr_codes_endpoint(
    batch_id: UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    batch = get_qr_batch(db, batch_id)

    if batch is None:
        raise HTTPException(
            status_code=404,
            detail="QR batch not found.",
        )

    codes = list_batch_qr_codes(
        db,
        batch_id,
        offset=offset,
        limit=limit,
    )

    public_base_url = get_public_base_url(db)
    return [
        {
            "id": code.id,
            "batch_id": code.batch_id,
            "token": code.token,
            "status": code.status,
            "created_at": code.created_at,
            "scan_url": get_qr_destination(code.token, public_base_url=public_base_url),
        }
        for code in codes
    ]


@router.get(
    "/codes/{qr_code_id}",
    response_model=QRCodeResponse,
)
def get_qr_code_endpoint(
    qr_code_id: UUID,
    db: Session = Depends(get_db),
):
    code = db.get(QRCode, qr_code_id)
    if code is None:
        raise HTTPException(status_code=404, detail="QR code not found.")
    public_base_url = get_public_base_url(db)
    return QRCodeResponse.model_validate({
        "id": code.id,
        "batch_id": code.batch_id,
        "token": code.token,
        "status": code.status,
        "created_at": code.created_at,
        "scan_url": get_qr_destination(code.token, public_base_url=public_base_url),
    })


@router.get(
    "/codes/{qr_code_id}/image",
)
def get_qr_image_endpoint(
    qr_code_id: UUID,
    image_format: str = Query(
        default="png",
        alias="format",
        pattern="^(png|svg)$",
    ),
    db: Session = Depends(get_db),
):
    qr_code = db.get(QRCode, qr_code_id)

    if qr_code is None:
        raise HTTPException(
            status_code=404,
            detail="QR code not found.",
        )

    destination = get_qr_destination(qr_code.token, db)
    qr = segno.make(destination, error="H")

    output = BytesIO()
    qr.save(
        output,
        kind=image_format,
        scale=6,
        border=4,
    )

    media_type = (
        "image/png" if image_format == "png"
        else "image/svg+xml"
    )

    return Response(
        content=output.getvalue(),
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'inline; filename="qr-{qr_code.id}.{image_format}"'
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )
