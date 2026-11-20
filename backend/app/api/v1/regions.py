from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import require_super_admin
from app.core.database import get_db
from app.schemas.region import (
    RegionBoundaryDeleteResponse,
    RegionBoundaryResponse,
    RegionBoundaryUpdate,
    RegionCreate,
    RegionResponse,
    RegionUpdate,
)
from app.models import AdminUser
from app.services.region_boundary_service import (
    RegionBoundaryInvalid,
    RegionBoundaryNotFound,
    delete_region_boundary,
    get_region_boundary,
    save_region_boundary,
)
from app.services.region_service import (
    RegionHierarchyCycle,
    RegionHasActiveChildren,
    RegionNotFound,
    RegionParentInactive,
    RegionParentNotFound,
    create_region,
    deactivate_region,
    get_region,
    list_regions,
    update_region,
)


router = APIRouter(
    prefix="/regions",
    tags=["Regions"],
    dependencies=[Depends(require_super_admin)],
)


@router.post(
    "",
    response_model=RegionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_region_endpoint(
    region_data: RegionCreate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return create_region(db, region_data, admin_id=actor.id)

    except RegionParentNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent region not found.",
        )

    except RegionParentInactive:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Regions cannot be assigned to an inactive parent.",
        )

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Region could not be created. The region code may already exist.",
        )


@router.get(
    "",
    response_model=list[RegionResponse],
)
def list_regions_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    is_active: bool | None = Query(default=None),
    parent_id: UUID | None = Query(default=None),
    region_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return list_regions(
        db,
        offset=offset,
        limit=limit,
        is_active=is_active,
        parent_id=parent_id,
        region_type=region_type,
    )


@router.get(
    "/{region_id}",
    response_model=RegionResponse,
)
def get_region_endpoint(
    region_id: UUID,
    db: Session = Depends(get_db),
):
    region = get_region(db, region_id)

    if region is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Region not found.",
        )

    return region


@router.patch(
    "/{region_id}",
    response_model=RegionResponse,
)
def update_region_endpoint(
    region_id: UUID,
    region_data: RegionUpdate,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return update_region(db, region_id, region_data, admin_id=actor.id)

    except RegionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Region not found.",
        )

    except RegionParentNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent region not found.",
        )

    except RegionParentInactive:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Regions cannot be assigned to an inactive parent.",
        )

    except RegionHierarchyCycle:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Region hierarchy would contain a cycle.",
        )

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Region could not be updated. The region code may already exist.",
        )


@router.delete(
    "/{region_id}",
    response_model=RegionResponse,
)
def deactivate_region_endpoint(
    region_id: UUID,
    actor: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return deactivate_region(db, region_id, admin_id=actor.id)

    except RegionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Region not found.",
        )

    except RegionHasActiveChildren:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Regions with active child regions cannot be deactivated.",
        )

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Region could not be deactivated.",
        )


@router.get(
    "/{region_id}/boundary",
    response_model=RegionBoundaryResponse,
)
def get_region_boundary_endpoint(
    region_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        return {"region_id": region_id, "geometry": get_region_boundary(db, region_id)}
    except RegionBoundaryNotFound:
        raise HTTPException(status_code=404, detail="Region not found.")


@router.put(
    "/{region_id}/boundary",
    response_model=RegionBoundaryResponse,
)
def save_region_boundary_endpoint(
    region_id: UUID,
    data: RegionBoundaryUpdate,
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        geometry = save_region_boundary(
            db,
            region_id=region_id,
            geometry=data.geometry.model_dump(),
            admin_id=admin.id,
        )
        return {"region_id": region_id, "geometry": geometry}
    except RegionBoundaryNotFound:
        raise HTTPException(status_code=404, detail="Region not found.")
    except RegionBoundaryInvalid:
        raise HTTPException(
            status_code=422,
            detail="Boundary must be a valid, non-empty 2D Polygon or MultiPolygon in longitude/latitude coordinates.",
        )
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Region boundary could not be saved.")


@router.delete(
    "/{region_id}/boundary",
    response_model=RegionBoundaryDeleteResponse,
)
def delete_region_boundary_endpoint(
    region_id: UUID,
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        delete_region_boundary(db, region_id=region_id, admin_id=admin.id)
        return {"deleted": True}
    except RegionBoundaryNotFound:
        raise HTTPException(status_code=404, detail="Region boundary not found.")
