from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth import require_super_admin
from app.core.database import get_db
from app.models import AdminUser
from app.schemas.location_policy import (
    LocationPolicyCreate,
    LocationPolicyUpdate,
    LocationPolicyResponse,
    LocationPolicyAssignmentCreate,
    LocationPolicyAssignmentResponse,
)
from app.services.location_policy_service import (
    LocationPolicyNotFound,
    LocationPolicyInactive,
    LocationPolicyActive,
    InvalidLocationPolicy,
    LocationPolicyAssignmentNotFound,
    AssignmentAlreadyExists,
    AssignmentTargetNotFound,
    AssignmentConflict,
    create_policy,
    get_policy,
    list_policies,
    update_policy,
    deactivate_policy,
    permanently_delete_policy,
    create_assignment,
    get_assignment,
    list_assignments,
    replace_assignment,
    delete_assignment,
)


router = APIRouter(tags=["Location Policies"])


def map_service_error(exc):
    if isinstance(
        exc,
        (LocationPolicyNotFound, LocationPolicyAssignmentNotFound),
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location policy or assignment not found.",
        ) from exc

    if isinstance(exc, AssignmentTargetNotFound):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The specified product or active region was not found.",
        ) from exc

    if isinstance(exc, LocationPolicyInactive):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot assign an inactive location policy.",
        ) from exc

    if isinstance(exc, LocationPolicyActive):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Deactivate the location policy before permanently deleting it.",
        ) from exc

    if isinstance(exc, AssignmentAlreadyExists):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An assignment already exists for this scope target.",
        ) from exc

    if isinstance(exc, AssignmentConflict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assignment conflicts with an existing database constraint.",
        ) from exc

    if isinstance(exc, InvalidLocationPolicy):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid location policy or assignment data.",
        ) from exc

    raise exc


# Policy endpoints

@router.post(
    "/location-policies",
    response_model=LocationPolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_location_policy_endpoint(
    data: LocationPolicyCreate,
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return create_policy(db, data, admin.id)


@router.get(
    "/location-policies",
    response_model=list[LocationPolicyResponse],
)
def list_location_policies_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    is_active: bool | None = Query(default=None),
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return list_policies(
        db,
        offset=offset,
        limit=limit,
        is_active=is_active,
    )


@router.get(
    "/location-policies/{policy_id}",
    response_model=LocationPolicyResponse,
)
def get_location_policy_endpoint(
    policy_id: UUID,
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return get_policy(db, policy_id)
    except LocationPolicyNotFound as exc:
        map_service_error(exc)


@router.patch(
    "/location-policies/{policy_id}",
    response_model=LocationPolicyResponse,
)
def update_location_policy_endpoint(
    policy_id: UUID,
    data: LocationPolicyUpdate,
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return update_policy(db, policy_id, data, admin.id)
    except (
        LocationPolicyNotFound,
        InvalidLocationPolicy,
    ) as exc:
        map_service_error(exc)


@router.delete(
    "/location-policies/{policy_id}",
    response_model=LocationPolicyResponse,
)
def deactivate_location_policy_endpoint(
    policy_id: UUID,
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return deactivate_policy(db, policy_id, admin.id)
    except LocationPolicyNotFound as exc:
        map_service_error(exc)


@router.delete(
    "/location-policies/{policy_id}/permanent",
)
def permanently_delete_location_policy_endpoint(
    policy_id: UUID,
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        permanently_delete_policy(db, policy_id, admin.id)
        return {"deleted": True}
    except (LocationPolicyNotFound, LocationPolicyActive) as exc:
        map_service_error(exc)


# Assignment endpoints

@router.post(
    "/location-policy-assignments",
    response_model=LocationPolicyAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_location_policy_assignment_endpoint(
    data: LocationPolicyAssignmentCreate,
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return create_assignment(db, data, admin.id)
    except (
        LocationPolicyNotFound,
        LocationPolicyInactive,
        InvalidLocationPolicy,
        AssignmentAlreadyExists,
        AssignmentTargetNotFound,
        AssignmentConflict,
    ) as exc:
        map_service_error(exc)


@router.get(
    "/location-policy-assignments",
    response_model=list[LocationPolicyAssignmentResponse],
)
def list_location_policy_assignments_endpoint(
    policy_id: UUID | None = Query(default=None),
    scope_type: str | None = Query(
        default=None,
        pattern="^(GLOBAL|PRODUCT|REGION)$",
    ),
    product_id: UUID | None = Query(default=None),
    region_id: UUID | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return list_assignments(
        db,
        policy_id=policy_id,
        scope_type=scope_type,
        product_id=product_id,
        region_id=region_id,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/location-policy-assignments/{assignment_id}",
    response_model=LocationPolicyAssignmentResponse,
)
def get_location_policy_assignment_endpoint(
    assignment_id: UUID,
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return get_assignment(db, assignment_id)
    except LocationPolicyAssignmentNotFound as exc:
        map_service_error(exc)


@router.put(
    "/location-policy-assignments/{assignment_id}",
    response_model=LocationPolicyAssignmentResponse,
)
def replace_location_policy_assignment_endpoint(
    assignment_id: UUID,
    data: LocationPolicyAssignmentCreate,
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return replace_assignment(db, assignment_id, data, admin.id)
    except (
        LocationPolicyNotFound,
        LocationPolicyInactive,
        InvalidLocationPolicy,
        LocationPolicyAssignmentNotFound,
        AssignmentAlreadyExists,
        AssignmentTargetNotFound,
        AssignmentConflict,
    ) as exc:
        map_service_error(exc)


@router.delete(
    "/location-policy-assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_location_policy_assignment_endpoint(
    assignment_id: UUID,
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        delete_assignment(db, assignment_id, admin.id)
    except LocationPolicyAssignmentNotFound as exc:
        map_service_error(exc)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
