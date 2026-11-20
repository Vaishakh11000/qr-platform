from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ProductCategory
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.audit_service import record_audit_event


class CategoryParentNotFound(Exception):
    pass


class CategoryNotFound(Exception):
    pass


class CategoryHierarchyCycle(Exception):
    pass


def create_category(
    db: Session,
    category_data: CategoryCreate,
    admin_id: UUID | None = None,
) -> ProductCategory:

    if category_data.parent_id is not None:
        parent = db.get(ProductCategory, category_data.parent_id)

        if parent is None:
            raise CategoryParentNotFound()

    category = ProductCategory(
        name=category_data.name,
        description=category_data.description,
        parent_id=category_data.parent_id,
    )

    db.add(category)

    try:
        db.flush()
        record_audit_event(
            db,
            admin_id=admin_id,
            action="CATEGORY_CREATED",
            entity_type="PRODUCT_CATEGORY",
            entity_id=category.id,
            new_values=_category_snapshot(category),
        )
        db.commit()
        db.refresh(category)
    except IntegrityError:
        db.rollback()
        raise

    return category


def list_categories(
    db: Session,
    *,
    offset: int = 0,
    limit: int = 50,
    is_active: bool | None = None,
    parent_id: UUID | None = None,
) -> list[ProductCategory]:

    query = select(ProductCategory)

    if is_active is not None:
        query = query.where(ProductCategory.is_active == is_active)

    if parent_id is not None:
        query = query.where(ProductCategory.parent_id == parent_id)

    query = (
        query
        .order_by(ProductCategory.name, ProductCategory.id)
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(query).all())


def get_category(
    db: Session,
    category_id: UUID,
) -> ProductCategory | None:

    return db.get(ProductCategory, category_id)


def update_category(
    db: Session,
    category_id: UUID,
    category_data: CategoryUpdate,
    admin_id: UUID | None = None,
) -> ProductCategory:

    category = db.get(ProductCategory, category_id)

    if category is None:
        raise CategoryNotFound()

    old_values = _category_snapshot(category)
    updates = category_data.model_dump(exclude_unset=True)

    if "parent_id" in updates:
        new_parent_id = updates["parent_id"]

        if new_parent_id is not None:
            if new_parent_id == category.id:
                raise CategoryHierarchyCycle()

            parent = db.get(ProductCategory, new_parent_id)

            if parent is None:
                raise CategoryParentNotFound()

            # Walk up the proposed parent's hierarchy.
            # The category being updated must not appear in that chain.
            current_parent = parent
            visited = set()

            while current_parent is not None:
                if current_parent.id == category.id:
                    raise CategoryHierarchyCycle()

                if current_parent.id in visited:
                    raise CategoryHierarchyCycle()

                visited.add(current_parent.id)

                if current_parent.parent_id is None:
                    break

                current_parent = db.get(
                    ProductCategory,
                    current_parent.parent_id,
                )

    for field, value in updates.items():
        setattr(category, field, value)

    try:
        action = "CATEGORY_UPDATED"
        if "is_active" in updates and updates["is_active"] != old_values["is_active"]:
            action = "CATEGORY_REACTIVATED" if updates["is_active"] else "CATEGORY_DEACTIVATED"
        record_audit_event(
            db,
            admin_id=admin_id,
            action=action,
            entity_type="PRODUCT_CATEGORY",
            entity_id=category.id,
            old_values=old_values,
            new_values=_category_snapshot(category),
        )
        db.commit()
        db.refresh(category)
    except IntegrityError:
        db.rollback()
        raise

    return category


def deactivate_category(
    db: Session,
    category_id: UUID,
    admin_id: UUID | None = None,
) -> ProductCategory:

    category = db.get(ProductCategory, category_id)

    if category is None:
        raise CategoryNotFound()

    old_values = _category_snapshot(category)
    category.is_active = False

    try:
        if old_values["is_active"]:
            record_audit_event(
                db,
                admin_id=admin_id,
                action="CATEGORY_DEACTIVATED",
                entity_type="PRODUCT_CATEGORY",
                entity_id=category.id,
                old_values=old_values,
                new_values=_category_snapshot(category),
            )
        db.commit()
        db.refresh(category)
    except IntegrityError:
        db.rollback()
        raise

    return category


def _category_snapshot(category: ProductCategory) -> dict:
    return {
        "name": category.name,
        "description": category.description,
        "parent_id": str(category.parent_id) if category.parent_id else None,
        "is_active": category.is_active,
    }
