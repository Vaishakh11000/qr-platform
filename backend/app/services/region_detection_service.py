from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Region, RegionBoundary


MAX_GPS_ACCURACY_METERS = 500


def detect_region(
    db: Session,
    *,
    latitude: float,
    longitude: float,
) -> Region | None:
    """
    Find the deepest active region whose boundary covers a GPS point.

    Returns None when:
    - No active region boundary contains the point.
    - Multiple matching regions have the same deepest hierarchy level.
    """

    point = func.ST_SetSRID(
        func.ST_MakePoint(longitude, latitude),
        4326,
    )

    candidates = db.execute(
        select(Region.id, Region.parent_id)
        .join(
            RegionBoundary,
            RegionBoundary.region_id == Region.id,
        )
        .where(
            Region.is_active.is_(True),
            func.ST_Covers(RegionBoundary.boundary, point),
        )
    ).all()

    if not candidates:
        return None

    # Build the hierarchy once so nested boundaries can be ranked.
    parent_rows = db.execute(
        select(Region.id, Region.parent_id)
    ).all()

    parents = {
        region_id: parent_id
        for region_id, parent_id in parent_rows
    }

    def hierarchy_depth(region_id):
        depth = 0
        current_id = region_id
        visited = set()

        while current_id is not None and current_id not in visited:
            visited.add(current_id)
            current_id = parents.get(current_id)

            if current_id is not None:
                depth += 1

        return depth

    ranked = [
        (region_id, hierarchy_depth(region_id))
        for region_id, _ in candidates
    ]

    deepest_depth = max(depth for _, depth in ranked)

    deepest_regions = [
        region_id
        for region_id, depth in ranked
        if depth == deepest_depth
    ]

    # Do not arbitrarily select between overlapping sibling regions.
    if len(deepest_regions) != 1:
        return None

    return db.get(Region, deepest_regions[0])


def classify_region(
    db: Session,
    *,
    assigned_region_id,
    detected_region_id,
) -> str:
    """
    A detected region matches when it is the allocated region
    or any descendant of the allocated region.
    """

    if assigned_region_id is None or detected_region_id is None:
        return "UNKNOWN"

    if assigned_region_id == detected_region_id:
        return "MATCH"

    parent_rows = db.execute(
        select(Region.id, Region.parent_id)
    ).all()

    parents = {
        region_id: parent_id
        for region_id, parent_id in parent_rows
    }

    current_id = detected_region_id
    visited = set()

    while current_id is not None and current_id not in visited:
        visited.add(current_id)
        current_id = parents.get(current_id)

        if current_id == assigned_region_id:
            return "MATCH"

    return "MISMATCH"


def resolve_scan_region(
    db: Session,
    *,
    assigned_region_id,
    latitude: float | None,
    longitude: float | None,
    accuracy_meters: float | None,
) -> tuple[Region | None, str]:
    """
    Resolve and classify a scan location.

    GPS accuracy above 500 metres or missing accuracy is treated
    as insufficient for geographic classification.
    """

    if (
        latitude is None
        or longitude is None
        or accuracy_meters is None
        or accuracy_meters > MAX_GPS_ACCURACY_METERS
    ):
        return None, "UNKNOWN"

    detected_region = detect_region(
        db,
        latitude=latitude,
        longitude=longitude,
    )

    classification = classify_region(
        db,
        assigned_region_id=assigned_region_id,
        detected_region_id=detected_region.id if detected_region else None,
    )

    return detected_region, classification
