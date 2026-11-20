from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Product,
    QRAllocation,
    QRBatch,
    QRCode,
    ScanClassification,
    ScanEvent,
)


def _count(db: Session, model, *conditions) -> int:
    query = select(func.count()).select_from(model)

    if conditions:
        query = query.where(*conditions)

    return db.scalar(query) or 0


def get_dashboard_overview(db: Session) -> dict:
    """Return live counts from the source tables."""

    allocated_qr_count = db.scalar(
        select(func.count(distinct(QRAllocation.qr_code_id))).where(
            QRAllocation.ended_at.is_(None)
        )
    ) or 0

    return {
        "products": {
            "total": _count(db, Product),
            "active": _count(db, Product, Product.status == "ACTIVE"),
            "draft": _count(db, Product, Product.status == "DRAFT"),
            "archived": _count(db, Product, Product.status == "ARCHIVED"),
        },
        "qr_codes": {
            "total": _count(db, QRCode),
            "active": _count(db, QRCode, QRCode.status == "ACTIVE"),
            "inactive": _count(db, QRCode, QRCode.status == "INACTIVE"),
            "revoked": _count(db, QRCode, QRCode.status == "REVOKED"),
            "allocated": allocated_qr_count,
        },
        "batches": {
            "total": _count(db, QRBatch),
            "generated": _count(
                db, QRBatch, QRBatch.generation_status == "GENERATED"
            ),
            "pending": _count(
                db, QRBatch, QRBatch.generation_status == "PENDING"
            ),
            "failed": _count(
                db, QRBatch, QRBatch.generation_status == "FAILED"
            ),
        },
        "scans": {
            "total": _count(db, ScanEvent),
            "pending": _count(
                db, ScanEvent, ScanEvent.result_status == "PENDING"
            ),
            "allowed": _count(
                db, ScanEvent, ScanEvent.result_status == "ALLOWED"
            ),
            "blocked": _count(
                db, ScanEvent, ScanEvent.result_status == "BLOCKED"
            ),
            "error": _count(
                db, ScanEvent, ScanEvent.result_status == "ERROR"
            ),
        },
    }


def get_scan_trends(db: Session, days: int = 30) -> list[dict]:
    """
    Return one row per UTC calendar date, including dates with no scans.
    The range includes today and the preceding days - 1 dates.
    """

    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days - 1)

    utc_scan_date = func.date(
        func.timezone("UTC", ScanEvent.scanned_at)
    )

    query = (
        select(
            utc_scan_date.label("scan_date"),
            func.count(ScanEvent.id).label("total"),
            func.sum(
                case((ScanEvent.result_status == "PENDING", 1), else_=0)
            ).label("pending"),
            func.sum(
                case((ScanEvent.result_status == "ALLOWED", 1), else_=0)
            ).label("allowed"),
            func.sum(
                case((ScanEvent.result_status == "BLOCKED", 1), else_=0)
            ).label("blocked"),
            func.sum(
                case((ScanEvent.result_status == "ERROR", 1), else_=0)
            ).label("error"),
        )
        .where(
            ScanEvent.scanned_at
            >= datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc),
            ScanEvent.scanned_at
            < datetime.combine(
                today + timedelta(days=1),
                datetime.min.time(),
                tzinfo=timezone.utc,
            ),
        )
        .group_by(utc_scan_date)
        .order_by(utc_scan_date)
    )

    rows = db.execute(query).all()
    counts_by_date = {
        row.scan_date: row
        for row in rows
    }

    result = []

    for offset in range(days):
        current_date = start_date + timedelta(days=offset)
        row = counts_by_date.get(current_date)

        result.append({
            "date": current_date,
            "total": int(row.total or 0) if row else 0,
            "pending": int(row.pending or 0) if row else 0,
            "allowed": int(row.allowed or 0) if row else 0,
            "blocked": int(row.blocked or 0) if row else 0,
            "error": int(row.error or 0) if row else 0,
        })

    return result


def get_location_analytics(db: Session) -> dict:
    """Return scan location-status and region-classification counts."""

    location_rows = db.execute(
        select(
            ScanEvent.location_status,
            func.count(ScanEvent.id),
        ).group_by(ScanEvent.location_status)
    ).all()

    classification_rows = db.execute(
        select(
            ScanClassification.classification,
            func.count(ScanClassification.id),
        ).group_by(ScanClassification.classification)
    ).all()

    location_counts = {
        "PENDING": 0,
        "GPS": 0,
        "IP_DERIVED": 0,
        "SKIPPED": 0,
        "DENIED": 0,
        "UNAVAILABLE": 0,
        "IP_LOOKUP_FAILED": 0,
        "UNCERTAIN": 0,
    }

    classification_counts = {
        "MATCH": 0,
        "MISMATCH": 0,
        "UNKNOWN": 0,
        "NOT_CHECKED": 0,
    }

    for status, count in location_rows:
        if status in location_counts:
            location_counts[status] = count

    for classification, count in classification_rows:
        if classification in classification_counts:
            classification_counts[classification] = count

    return {
        "location_statuses": location_counts,
        "classifications": classification_counts,
    }


def get_recent_activity(db: Session, limit: int = 10) -> list[AuditLog]:
    """Return recent audit records, newest first."""

    query = (
        select(AuditLog)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
    )

    return list(db.scalars(query).all())
