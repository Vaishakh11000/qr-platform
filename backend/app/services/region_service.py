from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Region
from app.schemas.region import RegionCreate, RegionUpdate
from app.services.audit_service import record_audit_event


class RegionParentNotFound(Exception):
    pass


class RegionParentInactive(Exception):
    pass


class RegionNotFound(Exception):
    pass


class RegionHierarchyCycle(Exception):
    pass


class RegionHasActiveChildren(Exception):
    pass


def create_region(
    db: Session,
    region_data: RegionCreate,
    admin_id: UUID | None = None,
) -> Region:
    if region_data.parent_id is not None:
        parent = db.get(Region, region_data.parent_id)

        if parent is None:
            raise RegionParentNotFound()

        if not parent.is_active:
            raise RegionParentInactive()

    region = Region(
        name=region_data.name,
        region_code=region_data.region_code,
        region_type=region_data.region_type,
        parent_id=region_data.parent_id,
    )

    db.add(region)

    try:
        db.flush()
        record_audit_event(
            db,
            admin_id=admin_id,
            action="REGION_CREATED",
            entity_type="REGION",
            entity_id=region.id,
            new_values=_region_snapshot(region),
        )
        db.commit()
        db.refresh(region)
    except IntegrityError:
        db.rollback()
        raise

    return region


def list_regions(
    db: Session,
    *,
    offset: int = 0,
    limit: int = 50,
    is_active: bool | None = None,
    parent_id: UUID | None = None,
    region_type: str | None = None,
) -> list[Region]:
    query = select(Region)

    if is_active is not None:
        query = query.where(Region.is_active == is_active)

    if parent_id is not None:
        query = query.where(Region.parent_id == parent_id)

    if region_type is not None:
        query = query.where(Region.region_type == region_type)

    query = (
        query
        .order_by(Region.name, Region.id)
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(query).all())


def get_region(
    db: Session,
    region_id: UUID,
) -> Region | None:
    return db.get(Region, region_id)


def update_region(
    db: Session,
    region_id: UUID,
    region_data: RegionUpdate,
    admin_id: UUID | None = None,
) -> Region:
    region = db.get(Region, region_id)

    if region is None:
        raise RegionNotFound()

    old_values = _region_snapshot(region)
    updates = region_data.model_dump(exclude_unset=True)

    if updates.get("is_active") is True and "parent_id" not in updates:
        if region.parent_id is not None:
            parent = db.get(Region, region.parent_id)

            if parent is None:
                raise RegionParentNotFound()

            if not parent.is_active:
                raise RegionParentInactive()

    if "parent_id" in updates:
        new_parent_id = updates["parent_id"]

        if new_parent_id is not None:
            if new_parent_id == region.id:
                raise RegionHierarchyCycle()

            parent = db.get(Region, new_parent_id)

            if parent is None:
                raise RegionParentNotFound()

            if not parent.is_active:
                raise RegionParentInactive()

            current_parent = parent
            visited = set()

            while current_parent is not None:
                if current_parent.id == region.id:
                    raise RegionHierarchyCycle()

                if current_parent.id in visited:
                    raise RegionHierarchyCycle()

                visited.add(current_parent.id)

                if current_parent.parent_id is None:
                    break

                current_parent = db.get(
                    Region,
                    current_parent.parent_id,
                )

    for field, value in updates.items():
        setattr(region, field, value)

    try:
        action = "REGION_UPDATED"
        if "is_active" in updates and updates["is_active"] != old_values["is_active"]:
            action = "REGION_REACTIVATED" if updates["is_active"] else "REGION_DEACTIVATED"
        record_audit_event(
            db,
            admin_id=admin_id,
            action=action,
            entity_type="REGION",
            entity_id=region.id,
            old_values=old_values,
            new_values=_region_snapshot(region),
        )
        db.commit()
        db.refresh(region)
    except IntegrityError:
        db.rollback()
        raise

    return region


def deactivate_region(
    db: Session,
    region_id: UUID,
    admin_id: UUID | None = None,
) -> Region:
    region = db.get(Region, region_id)

    if region is None:
        raise RegionNotFound()

    active_child_exists = db.scalar(
        select(Region.id)
        .where(
            Region.parent_id == region_id,
            Region.is_active.is_(True),
        )
        .limit(1)
    )
    if active_child_exists is not None:
        raise RegionHasActiveChildren()

    old_values = _region_snapshot(region)
    region.is_active = False

    try:
        if old_values["is_active"]:
            record_audit_event(
                db,
                admin_id=admin_id,
                action="REGION_DEACTIVATED",
                entity_type="REGION",
                entity_id=region.id,
                old_values=old_values,
                new_values=_region_snapshot(region),
            )
        db.commit()
        db.refresh(region)
    except IntegrityError:
        db.rollback()
        raise

    return region


def _region_snapshot(region: Region) -> dict:
    return {
        "name": region.name,
        "region_code": region.region_code,
        "region_type": region.region_type,
        "parent_id": str(region.parent_id) if region.parent_id else None,
        "is_active": region.is_active,
    }
