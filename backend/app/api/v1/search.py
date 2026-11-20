from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from uuid import NAMESPACE_URL, uuid5

from app.core.auth import require_super_admin
from app.core.database import get_db
from app.models import (
    AuditLog,
    Form,
    LocationPolicy,
    Product,
    ProductCategory,
    ProductVersion,
    QRBatch,
    QRCode,
    Region,
)
from app.schemas.search import SearchResponse, SearchResult


router = APIRouter(
    prefix="/search",
    tags=["Search"],
    dependencies=[Depends(require_super_admin)],
)


SETTING_SEARCH_OPTIONS = (
    ("public-qr-address", "Public QR address", "Set the customer-facing website used by QR links.", "public qr website url address domain base url link phone accessible", "public-qr-address"),
    ("gps-collection", "GPS collection settings", "Browser GPS permissions and location policy configuration.", "gps location permission collection policy geolocation", "integration-gps"),
    ("ip-geolocation", "IP geolocation integration", "Provider and backend integration status for IP location fallback.", "ip geolocation fallback provider credentials integration", "integration-ip-geolocation"),
    ("email-push-delivery", "Email and push delivery", "Notification delivery provider and integration status.", "email push notification delivery provider alerts", "integration-email-push"),
    ("product-media-storage", "Product media storage", "Persistent product image storage and deployment configuration.", "product media image file storage volume backup", "integration-media-storage"),
    ("administrator-access", "Administrator access", "Create, activate, or deactivate administrator accounts.", "administrator admin user access account permissions", "administrators"),
)


@router.get("", response_model=SearchResponse)
def search_platform(
    q: str = Query(min_length=2, max_length=100),
    db: Session = Depends(get_db),
):
    query = q.strip()
    if len(query) < 2:
        return SearchResponse(query=query, items=[])

    escaped_query = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped_query}%"
    results: list[SearchResult] = []

    for product in db.scalars(
        select(Product)
        .outerjoin(
            ProductVersion,
            ProductVersion.id == Product.current_version_id,
        )
        .where(or_(
            Product.name.ilike(pattern, escape="\\"),
            Product.sku.ilike(pattern, escape="\\"),
            Product.short_description.ilike(pattern, escape="\\"),
            ProductVersion.content_snapshot["specifications"].astext.ilike(
                pattern, escape="\\"
            ),
        ))
        .order_by(Product.name, Product.id)
        .limit(8)
    ):
        results.append(SearchResult(
            id=product.id,
            kind="Product",
            title=product.name,
            detail=f"SKU {product.sku} · {product.status}",
            page="Products",
        ))

    for category in db.scalars(
        select(ProductCategory)
        .where(ProductCategory.name.ilike(pattern, escape="\\"))
        .order_by(ProductCategory.name, ProductCategory.id)
        .limit(8)
    ):
        results.append(SearchResult(
            id=category.id,
            kind="Category",
            title=category.name,
            detail="Active" if category.is_active else "Inactive",
            page="Categories",
        ))

    for region in db.scalars(
        select(Region)
        .where(or_(Region.name.ilike(pattern, escape="\\"), Region.region_code.ilike(pattern, escape="\\")))
        .order_by(Region.name, Region.id)
        .limit(8)
    ):
        results.append(SearchResult(
            id=region.id,
            kind="Region",
            title=region.name,
            detail=f"{region.region_code} · {region.region_type}",
            page="Regions",
        ))

    for batch in db.scalars(
        select(QRBatch)
        .where(QRBatch.batch_code.ilike(pattern, escape="\\"))
        .order_by(QRBatch.created_at.desc(), QRBatch.id)
        .limit(8)
    ):
        results.append(SearchResult(
            id=batch.id,
            kind="QR batch",
            title=batch.batch_code,
            detail=f"{batch.quantity} codes · {batch.generation_status}",
            page="QR Batches",
        ))

    for code, batch_code in db.execute(
        select(QRCode, QRBatch.batch_code)
        .join(QRBatch, QRBatch.id == QRCode.batch_id)
        .where(QRCode.token.ilike(pattern, escape="\\"))
        .order_by(QRCode.created_at.desc(), QRCode.id)
        .limit(8)
    ):
        results.append(SearchResult(
            id=code.id,
            kind="QR code",
            title=f"QR code · …{code.token[-8:]}",
            detail=f"Batch {batch_code} · {code.status}",
            page="QR Codes",
        ))

    for policy in db.scalars(
        select(LocationPolicy)
        .where(LocationPolicy.name.ilike(pattern, escape="\\"))
        .order_by(LocationPolicy.name, LocationPolicy.id)
        .limit(8)
    ):
        results.append(SearchResult(
            id=policy.id,
            kind="Location policy",
            title=policy.name,
            detail=f"{policy.requirement} · {policy.method}",
            page="Location Policies",
        ))

    for form in db.scalars(
        select(Form)
        .where(Form.name.ilike(pattern, escape="\\"))
        .order_by(Form.name, Form.id)
        .limit(8)
    ):
        results.append(SearchResult(
            id=form.id,
            kind="Form",
            title=form.name,
            detail=form.description,
            page="Forms",
        ))

    for log in db.scalars(
        select(AuditLog)
        .where(or_(AuditLog.action.ilike(pattern, escape="\\"), AuditLog.entity_type.ilike(pattern, escape="\\")))
        .order_by(AuditLog.created_at.desc(), AuditLog.id)
        .limit(8)
    ):
        results.append(SearchResult(
            id=log.id,
            kind="Audit event",
            title=log.action,
            detail=f"{log.entity_type} · {log.created_at.isoformat()}",
            page="Audit Logs",
        ))

    normalized_query = query.casefold()
    for key, title, detail, search_terms, target_key in SETTING_SEARCH_OPTIONS:
        if normalized_query in f"{title} {detail} {search_terms}".casefold():
            results.append(SearchResult(
                id=uuid5(NAMESPACE_URL, f"qr-platform-setting:{key}"),
                kind="Setting",
                title=title,
                detail=detail,
                page="Administration",
                target_key=target_key,
            ))

    return SearchResponse(query=query, items=results[:50])
