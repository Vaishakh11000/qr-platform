from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Product, ProductVersion
from app.schemas.product_version import (
    ProductVersionCreate,
    ProductVersionUpdate,
)
from app.services.audit_service import record_audit_event


class VersionProductNotFound(Exception):
    pass


class VersionNotFound(Exception):
    pass


class VersionProductArchived(Exception):
    pass


class VersionNotDraft(Exception):
    pass


class VersionNotPublishable(Exception):
    pass


def create_product_version(
    db: Session,
    product_id: UUID,
    version_data: ProductVersionCreate,
    admin_id: UUID | None = None,
) -> ProductVersion:

    # Lock the product row to serialize version-number allocation.
    product = db.execute(
        select(Product)
        .where(Product.id == product_id)
        .with_for_update()
    ).scalar_one_or_none()

    if product is None:
        raise VersionProductNotFound()

    if product.status == "ARCHIVED":
        raise VersionProductArchived()

    latest_version_number = db.scalar(
        select(func.coalesce(func.max(ProductVersion.version_number), 0))
        .where(ProductVersion.product_id == product_id)
    )

    version = ProductVersion(
        product_id=product_id,
        version_number=latest_version_number + 1,
        content_snapshot=version_data.content_snapshot,
        status="DRAFT",
        created_by=admin_id,
    )

    db.add(version)

    try:
        db.flush()
        record_audit_event(
            db,
            admin_id=admin_id,
            action="PRODUCT_VERSION_CREATED",
            entity_type="PRODUCT_VERSION",
            entity_id=version.id,
            new_values=_version_snapshot(version),
        )
        db.commit()
        db.refresh(version)
    except IntegrityError:
        db.rollback()
        raise

    return version


def list_product_versions(
    db: Session,
    product_id: UUID,
) -> list[ProductVersion]:

    product = db.get(Product, product_id)

    if product is None:
        raise VersionProductNotFound()

    query = (
        select(ProductVersion)
        .where(ProductVersion.product_id == product_id)
        .order_by(ProductVersion.version_number.desc())
    )

    return list(db.scalars(query).all())


def get_product_version(
    db: Session,
    product_id: UUID,
    version_id: UUID,
) -> ProductVersion | None:

    return db.scalar(
        select(ProductVersion).where(
            ProductVersion.id == version_id,
            ProductVersion.product_id == product_id,
        )
    )


def update_product_version(
    db: Session,
    product_id: UUID,
    version_id: UUID,
    version_data: ProductVersionUpdate,
    admin_id: UUID | None = None,
) -> ProductVersion:

    version = db.execute(
        select(ProductVersion)
        .where(
            ProductVersion.id == version_id,
            ProductVersion.product_id == product_id,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if version is None:
        raise VersionNotFound()

    if version.status != "DRAFT":
        raise VersionNotDraft()

    old_values = _version_snapshot(version)
    updates = version_data.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(version, field, value)

    try:
        if updates:
            db.flush()
            record_audit_event(
                db,
                admin_id=admin_id,
                action="PRODUCT_VERSION_UPDATED",
                entity_type="PRODUCT_VERSION",
                entity_id=version.id,
                old_values=old_values,
                new_values=_version_snapshot(version),
            )
        db.commit()
        db.refresh(version)
    except IntegrityError:
        db.rollback()
        raise

    return version


def publish_product_version(
    db: Session,
    product_id: UUID,
    version_id: UUID,
    admin_id: UUID | None = None,
) -> ProductVersion:

    # Lock the product first so all publishing operations for this
    # product are serialized.
    product = db.execute(
        select(Product)
        .where(Product.id == product_id)
        .with_for_update()
    ).scalar_one_or_none()

    if product is None:
        raise VersionProductNotFound()

    if product.status == "ARCHIVED":
        raise VersionProductArchived()

    version = db.execute(
        select(ProductVersion)
        .where(
            ProductVersion.id == version_id,
            ProductVersion.product_id == product_id,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if version is None:
        raise VersionNotFound()

    if version.status != "DRAFT":
        raise VersionNotDraft()

    previous_version = None

    if product.current_version_id is not None:
        previous_version = db.execute(
            select(ProductVersion)
            .where(
                ProductVersion.id == product.current_version_id,
                ProductVersion.product_id == product_id,
            )
            .with_for_update()
        ).scalar_one_or_none()

        if previous_version is None:
            raise VersionNotPublishable()

        if previous_version.status != "PUBLISHED":
            raise VersionNotPublishable()

    try:
        old_values = {
            "version": _version_snapshot(version),
            "product_status": product.status,
            "current_version_id": str(product.current_version_id) if product.current_version_id else None,
        }
        if previous_version is not None:
            previous_version.status = "RETIRED"

        version.status = "PUBLISHED"
        version.published_at = datetime.now(timezone.utc)
        version.published_by = admin_id
        db.flush()

        product.current_version_id = version.id
        product.status = "ACTIVE"
        product.updated_at = func.now()

        record_audit_event(
            db,
            admin_id=admin_id,
            action="PRODUCT_VERSION_PUBLISHED",
            entity_type="PRODUCT_VERSION",
            entity_id=version.id,
            old_values=old_values,
            new_values={
                "version": _version_snapshot(version),
                "product_status": product.status,
                "current_version_id": str(product.current_version_id),
                "previous_version_id": str(previous_version.id) if previous_version else None,
            },
        )

        db.commit()
        db.refresh(version)

    except IntegrityError:
        db.rollback()
        raise

    return version


def _version_snapshot(version: ProductVersion) -> dict:
    serialized = json.dumps(version.content_snapshot, sort_keys=True, default=str).encode()
    return {
        "product_id": str(version.product_id),
        "version_number": version.version_number,
        "status": version.status,
        "content_sha256": hashlib.sha256(serialized).hexdigest(),
    }
