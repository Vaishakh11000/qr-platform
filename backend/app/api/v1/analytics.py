from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.auth import require_super_admin
from app.core.database import get_db
from app.models import (
    AdminUser,
    Product,
    QRBatch,
    QRCode,
    Region,
    ScanClassification,
    ScanEvent,
)
from app.schemas.analytics import ScanAnalyticsResponse


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
    dependencies=[Depends(require_super_admin)],
)

RESULT_STATUSES = ("PENDING", "ALLOWED", "BLOCKED", "ERROR")
LOCATION_STATUSES = (
    "PENDING", "GPS", "IP_DERIVED", "SKIPPED", "DENIED",
    "UNAVAILABLE", "IP_LOOKUP_FAILED", "UNCERTAIN",
)
CLASSIFICATIONS = ("MATCH", "MISMATCH", "UNKNOWN", "NOT_CHECKED")
MAX_RANGE_DAYS = 366
BREAKDOWN_LIMIT = 100


def _scan_filters(
    *,
    start: datetime,
    end_exclusive: datetime,
    product_id: UUID | None,
    qr_code_id: UUID | None,
    region_id: UUID | None,
    result_status: str | None,
    location_status: str | None,
):
    filters = [ScanEvent.scanned_at >= start, ScanEvent.scanned_at < end_exclusive]
    if product_id is not None:
        filters.append(ScanEvent.product_id == product_id)
    if qr_code_id is not None:
        filters.append(ScanEvent.qr_code_id == qr_code_id)
    if region_id is not None:
        filters.append(ScanEvent.region_id == region_id)
    if result_status is not None:
        filters.append(ScanEvent.result_status == result_status)
    if location_status is not None:
        filters.append(ScanEvent.location_status == location_status)
    return filters


@router.get("/scans", response_model=ScanAnalyticsResponse)
def get_scan_analytics(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    product_id: UUID | None = Query(default=None),
    qr_code_id: UUID | None = Query(default=None),
    region_id: UUID | None = Query(default=None),
    result_status: Literal["PENDING", "ALLOWED", "BLOCKED", "ERROR"] | None = Query(default=None),
    location_status: Literal[
        "PENDING", "GPS", "IP_DERIVED", "SKIPPED", "DENIED",
        "UNAVAILABLE", "IP_LOOKUP_FAILED", "UNCERTAIN",
    ] | None = Query(default=None),
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    today = datetime.now(timezone.utc).date()
    end_date = to_date or today
    start_date = from_date or end_date - timedelta(days=29)
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="from_date must not be later than to_date.")
    if (end_date - start_date).days + 1 > MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 366 days.")

    start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_exclusive = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    filters = _scan_filters(
        start=start,
        end_exclusive=end_exclusive,
        product_id=product_id,
        qr_code_id=qr_code_id,
        region_id=region_id,
        result_status=result_status,
        location_status=location_status,
    )

    result_rows = db.execute(
        select(ScanEvent.result_status, func.count(ScanEvent.id))
        .where(*filters)
        .group_by(ScanEvent.result_status)
    ).all()
    summary_values = {key: 0 for key in RESULT_STATUSES}
    for status, count in result_rows:
        summary_values[status] = count
    summary = {"total": sum(summary_values.values()), **{
        "pending": summary_values["PENDING"],
        "allowed": summary_values["ALLOWED"],
        "blocked": summary_values["BLOCKED"],
        "error": summary_values["ERROR"],
    }}

    location_values = {key: 0 for key in LOCATION_STATUSES}
    for status, count in db.execute(
        select(ScanEvent.location_status, func.count(ScanEvent.id))
        .where(*filters)
        .group_by(ScanEvent.location_status)
    ):
        location_values[status] = count

    classification_values = {key: 0 for key in CLASSIFICATIONS}
    for classification, count in db.execute(
        select(ScanClassification.classification, func.count(ScanClassification.id))
        .join(ScanEvent, ScanEvent.id == ScanClassification.scan_event_id)
        .where(*filters)
        .group_by(ScanClassification.classification)
    ):
        classification_values[classification] = count

    utc_scan_date = func.date(func.timezone("UTC", ScanEvent.scanned_at))
    trend_rows = db.execute(
        select(
            utc_scan_date.label("scan_date"),
            func.count(ScanEvent.id).label("total"),
            func.sum(case((ScanEvent.result_status == "PENDING", 1), else_=0)).label("pending"),
            func.sum(case((ScanEvent.result_status == "ALLOWED", 1), else_=0)).label("allowed"),
            func.sum(case((ScanEvent.result_status == "BLOCKED", 1), else_=0)).label("blocked"),
            func.sum(case((ScanEvent.result_status == "ERROR", 1), else_=0)).label("error"),
        )
        .where(*filters)
        .group_by(utc_scan_date)
        .order_by(utc_scan_date)
    ).all()
    by_date = {row.scan_date: row for row in trend_rows}
    daily = []
    for offset in range((end_date - start_date).days + 1):
        current_date = start_date + timedelta(days=offset)
        row = by_date.get(current_date)
        daily.append({
            "date": current_date,
            "total": int(row.total or 0) if row else 0,
            "pending": int(row.pending or 0) if row else 0,
            "allowed": int(row.allowed or 0) if row else 0,
            "blocked": int(row.blocked or 0) if row else 0,
            "error": int(row.error or 0) if row else 0,
        })

    products = db.execute(
        select(
            ScanEvent.product_id,
            Product.name,
            Product.sku,
            func.count(ScanEvent.id).label("scans"),
        )
        .outerjoin(Product, Product.id == ScanEvent.product_id)
        .where(*filters)
        .group_by(ScanEvent.product_id, Product.name, Product.sku)
        .order_by(func.count(ScanEvent.id).desc(), Product.name)
        .limit(BREAKDOWN_LIMIT)
    ).all()
    regions = db.execute(
        select(
            ScanEvent.region_id,
            Region.name,
            Region.region_code,
            func.count(ScanEvent.id).label("scans"),
        )
        .outerjoin(Region, Region.id == ScanEvent.region_id)
        .where(*filters)
        .group_by(ScanEvent.region_id, Region.name, Region.region_code)
        .order_by(func.count(ScanEvent.id).desc(), Region.name)
        .limit(BREAKDOWN_LIMIT)
    ).all()
    qr_codes = db.execute(
        select(
            QRCode.id,
            QRBatch.batch_code,
            func.right(QRCode.token, 6).label("token_suffix"),
            func.count(ScanEvent.id).label("scans"),
        )
        .join(QRCode, QRCode.id == ScanEvent.qr_code_id)
        .join(QRBatch, QRBatch.id == QRCode.batch_id)
        .where(*filters)
        .group_by(QRCode.id, QRBatch.batch_code, QRCode.token)
        .order_by(func.count(ScanEvent.id).desc(), QRBatch.batch_code)
        .limit(BREAKDOWN_LIMIT)
    ).all()

    return {
        "from_date": start_date,
        "to_date": end_date,
        "summary": summary,
        "location_analytics": {
            "location_statuses": location_values,
            "classifications": classification_values,
        },
        "daily": daily,
        "products": [
            {"product_id": row.product_id, "name": row.name or "Unallocated", "sku": row.sku, "scans": row.scans}
            for row in products
        ],
        "regions": [
            {"region_id": row.region_id, "name": row.name or "Unassigned", "region_code": row.region_code, "scans": row.scans}
            for row in regions
        ],
        "qr_codes": [
            {"qr_code_id": row.id, "batch_code": row.batch_code, "token_suffix": row.token_suffix, "scans": row.scans}
            for row in qr_codes
        ],
    }
