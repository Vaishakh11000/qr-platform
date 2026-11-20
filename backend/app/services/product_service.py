from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Product, ProductCategory
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.audit_service import record_audit_event


class ProductNotFound(Exception):
    pass


class ProductCategoryNotFound(Exception):
    pass


class ProductCategoryInactive(Exception):
    pass


def validate_product_category(
    db: Session,
    category_id: UUID | None,
) -> None:
    if category_id is None:
        return

    category = db.get(ProductCategory, category_id)

    if category is None:
        raise ProductCategoryNotFound()

    if not category.is_active:
        raise ProductCategoryInactive()


def create_product(
    db: Session,
    product_data: ProductCreate,
    admin_id: UUID | None = None,
) -> Product:

    validate_product_category(db, product_data.category_id)

    product = Product(
        sku=product_data.sku,
        name=product_data.name,
        category_id=product_data.category_id,
        short_description=product_data.short_description,
        created_by=admin_id,
    )

    db.add(product)

    try:
        db.flush()
        record_audit_event(
            db,
            admin_id=admin_id,
            action="PRODUCT_CREATED",
            entity_type="PRODUCT",
            entity_id=product.id,
            new_values=_product_snapshot(product),
        )
        db.commit()
        db.refresh(product)
    except IntegrityError:
        db.rollback()
        raise

    return product


def list_products(
    db: Session,
    *,
    offset: int = 0,
    limit: int = 50,
    category_id: UUID | None = None,
    product_status: str | None = None,
) -> list[Product]:

    query = select(Product)

    if category_id is not None:
        query = query.where(Product.category_id == category_id)

    if product_status is not None:
        query = query.where(Product.status == product_status)

    query = (
        query
        .order_by(Product.created_at.desc(), Product.id)
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(query).all())


def get_product(
    db: Session,
    product_id: UUID,
) -> Product | None:

    return db.get(Product, product_id)


def update_product(
    db: Session,
    product_id: UUID,
    product_data: ProductUpdate,
    admin_id: UUID | None = None,
) -> Product:

    product = db.get(Product, product_id)

    if product is None:
        raise ProductNotFound()

    old_values = _product_snapshot(product)
    updates = product_data.model_dump(exclude_unset=True)

    if (
        "category_id" in updates
        and updates["category_id"] != product.category_id
    ):
        validate_product_category(db, updates["category_id"])

    for field, value in updates.items():
        setattr(product, field, value)

    product.updated_at = func.now()

    try:
        record_audit_event(
            db,
            admin_id=admin_id,
            action="PRODUCT_UPDATED",
            entity_type="PRODUCT",
            entity_id=product.id,
            old_values=old_values,
            new_values=_product_snapshot(product),
        )
        db.commit()
        db.refresh(product)
    except IntegrityError:
        db.rollback()
        raise

    return product


def archive_product(
    db: Session,
    product_id: UUID,
    admin_id: UUID | None = None,
) -> Product:

    product = db.get(Product, product_id)

    if product is None:
        raise ProductNotFound()

    old_values = _product_snapshot(product)
    product.status = "ARCHIVED"
    product.updated_at = func.now()

    try:
        if old_values["status"] != "ARCHIVED":
            record_audit_event(
                db,
                admin_id=admin_id,
                action="PRODUCT_ARCHIVED",
                entity_type="PRODUCT",
                entity_id=product.id,
                old_values=old_values,
                new_values=_product_snapshot(product),
            )
        db.commit()
        db.refresh(product)
    except IntegrityError:
        db.rollback()
        raise

    return product


def _product_snapshot(product: Product) -> dict:
    return {
        "sku": product.sku,
        "name": product.name,
        "category_id": str(product.category_id) if product.category_id else None,
        "short_description": product.short_description,
        "status": product.status,
        "current_version_id": str(product.current_version_id) if product.current_version_id else None,
    }
