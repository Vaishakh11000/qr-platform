import hashlib
import json
from uuid import UUID, uuid4

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import DataError, ProgrammingError
from sqlalchemy.orm import Session

from app.models import Region, RegionBoundary
from app.services.audit_service import record_audit_event


class RegionBoundaryNotFound(Exception):
    pass


class RegionBoundaryInvalid(Exception):
    pass


def get_region_boundary(db: Session, region_id: UUID) -> dict | None:
    if db.get(Region, region_id) is None:
        raise RegionBoundaryNotFound()
    value = db.scalar(
        select(func.ST_AsGeoJSON(RegionBoundary.boundary)).where(
            RegionBoundary.region_id == region_id
        )
    )
    return json.loads(value) if value else None


def _geometry_expression(payload: str):
    return func.ST_SetSRID(
        func.ST_Multi(func.ST_GeomFromGeoJSON(payload)),
        4326,
    )


def save_region_boundary(
    db: Session,
    *,
    region_id: UUID,
    geometry: dict,
    admin_id: UUID,
) -> dict:
    if db.get(Region, region_id) is None:
        raise RegionBoundaryNotFound()

    try:
        payload = json.dumps(geometry, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RegionBoundaryInvalid() from exc
    if len(payload.encode("utf-8")) > 2_000_000:
        raise RegionBoundaryInvalid()

    candidate = _geometry_expression(payload)
    try:
        valid, empty, geometry_type, dimensions, west, east, south, north = db.execute(
            select(
                func.ST_IsValid(candidate),
                func.ST_IsEmpty(candidate),
                func.GeometryType(candidate),
                func.ST_NDims(candidate),
                func.ST_XMin(candidate),
                func.ST_XMax(candidate),
                func.ST_YMin(candidate),
                func.ST_YMax(candidate),
            )
        ).one()
    except (DataError, ProgrammingError, ValueError) as exc:
        db.rollback()
        raise RegionBoundaryInvalid() from exc

    if (
        not valid
        or empty
        or geometry_type != "MULTIPOLYGON"
        or dimensions != 2
        or west < -180
        or east > 180
        or south < -90
        or north > 90
    ):
        raise RegionBoundaryInvalid()

    existing = db.scalar(
        select(RegionBoundary).where(RegionBoundary.region_id == region_id)
    )
    old_geojson = db.scalar(
        select(func.ST_AsGeoJSON(RegionBoundary.boundary)).where(
            RegionBoundary.region_id == region_id
        )
    )
    old_hash = hashlib.sha256(old_geojson.encode("utf-8")).hexdigest() if old_geojson else None
    new_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    if existing is None:
        boundary_id = uuid4()
        db.execute(
            insert(RegionBoundary).values(
                id=boundary_id,
                region_id=region_id,
                boundary=candidate,
            )
        )
    else:
        boundary_id = existing.id
        db.execute(
            update(RegionBoundary)
            .where(RegionBoundary.id == boundary_id)
            .values(boundary=candidate, updated_at=func.now())
        )

    record_audit_event(
        db,
        admin_id=admin_id,
        action="REGION_BOUNDARY_UPDATED" if existing else "REGION_BOUNDARY_CREATED",
        entity_type="REGION_BOUNDARY",
        entity_id=boundary_id,
        old_values={"sha256": old_hash} if old_hash else None,
        new_values={"sha256": new_hash, "geometry_type": "MULTIPOLYGON"},
    )
    db.commit()
    return get_region_boundary(db, region_id)


def delete_region_boundary(
    db: Session,
    *,
    region_id: UUID,
    admin_id: UUID,
) -> None:
    if db.get(Region, region_id) is None:
        raise RegionBoundaryNotFound()
    existing = db.scalar(
        select(RegionBoundary).where(RegionBoundary.region_id == region_id)
    )
    if existing is None:
        raise RegionBoundaryNotFound()

    old_geojson = db.scalar(
        select(func.ST_AsGeoJSON(RegionBoundary.boundary)).where(
            RegionBoundary.region_id == region_id
        )
    )
    old_hash = hashlib.sha256(old_geojson.encode("utf-8")).hexdigest()
    db.execute(delete(RegionBoundary).where(RegionBoundary.id == existing.id))
    record_audit_event(
        db,
        admin_id=admin_id,
        action="REGION_BOUNDARY_DELETED",
        entity_type="REGION_BOUNDARY",
        entity_id=existing.id,
        old_values={"sha256": old_hash},
        new_values=None,
    )
    db.commit()
